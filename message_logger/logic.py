import asyncio
import json
import io
import aiohttp
from sqlalchemy.orm import Session
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from . import database
from .minio_client import MinioClient

async def _process_file_component(
    component_id: int, 
    component_data: dict, 
    minio_client: MinioClient, 
    bucket_name: str,
    db_engine
):
    """下载文件、上传到 MinIO 并更新数据库"""
    file_url = component_data.get("url")
    file_name = component_data.get("file")

    if not file_url or not file_name:
        logger.warning(f"组件 {component_id} 缺少 URL 或文件名，跳过文件处理。")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status != 200:
                    logger.error(f"下载文件失败 (状态码: {response.status}): {file_url}")
                    return
                file_content = await response.read()
        
        file_stream = io.BytesIO(file_content)
        minio_client.upload_file(
            bucket_name=bucket_name,
            object_name=file_name,
            data=file_stream,
            length=len(file_content)
        )
        logger.info(f"文件 '{file_name}' 已成功上传到 MinIO。")

        new_file_record = database.File(
            component_fk=component_id,
            file_name=file_name,
            minio_path=f"/{bucket_name}/{file_name}",
            upload_timestamp=int(asyncio.get_event_loop().time())
        )
        
        with database.get_session(db_engine) as session:
            session.add(new_file_record)
            session.commit()
        logger.info(f"文件记录已为组件 {component_id} 存入数据库。")

    except Exception as e:
        logger.error(f"处理文件组件 {component_id} 时发生错误: {e}", exc_info=True)


def handle_message_event(
    event: AstrMessageEvent, 
    session: Session, 
    minio_client: MinioClient, 
    bucket_name: str,
    db_engine
):
    """处理消息事件，将其存入数据库并触发文件上传任务"""
    try:
        message_obj_dict = event.message_obj.to_dict()
        
        new_message = database.Message(
            message_id=str(message_obj_dict.get("message_id")),
            session_id=str(message_obj_dict.get("session_id")),
            sender_id=str(event.get_sender_id()),
            timestamp=message_obj_dict.get("timestamp"),
            raw_message_obj=json.dumps(message_obj_dict, ensure_ascii=False)
        )

        session.add(new_message)
        session.commit()
        session.refresh(new_message)

        for i, component_dict in enumerate(message_obj_dict.get("message", [])):
            new_component = database.MessageComponent(
                message_fk=new_message.id,
                order_index=i,
                component_type=component_dict.get("type"),
                component_data=json.dumps(component_dict, ensure_ascii=False)
            )
            session.add(new_component)
            session.commit()
            session.refresh(new_component)
            
            if new_component.component_type in ["Image", "Video", "File"]:
                asyncio.create_task(
                    _process_file_component(
                        new_component.id, 
                        component_dict, 
                        minio_client, 
                        bucket_name,
                        db_engine
                    )
                )

        logger.info(f"消息 {new_message.message_id} 及其组件已存入数据库。")

    except Exception as e:
        logger.error(f"处理消息时发生错误: {e}", exc_info=True)
        session.rollback()