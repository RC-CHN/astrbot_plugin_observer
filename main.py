import asyncio
from sqlalchemy.orm import Session
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

from .message_logger import database, logic
from .message_logger.minio_client import MinioClient

@register("observer", "RC-CHN", "将所有消息记录到数据库和 MinIO", "1.0.0")
class MessageLoggerPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.db_engine = None
        self.db_session: Session | None = None
        self.minio_client: MinioClient | None = None
        self.minio_bucket_name = ""

    async def initialize(self):
        """初始化插件，连接数据库和 MinIO。"""
        logger.info("初始化 Message Logger 插件...")
        
        # 1. 初始化数据库
        try:
            db_type = self.config.get("db_type", "postgresql")
            db_user = self.config.get("db_user")
            db_password = self.config.get("db_password")
            db_host = self.config.get("db_host")
            db_port = self.config.get("db_port")
            db_name = self.config.get("db_name")

            if db_type == "postgresql":
                db_uri = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            elif db_type == "mysql":
                db_uri = f"mysql+mysqlclient://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            else:
                db_uri = f"sqlite:///data/observer/messages.db"
                import os
                os.makedirs("data/observer", exist_ok=True)

            self.db_engine = database.get_engine(db_uri)
            database.init_db(self.db_engine)
            self.db_session = database.get_session(self.db_engine)
            logger.info(f"数据库已连接并初始化 (类型: {db_type})。")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            return

        # 2. 初始化 MinIO
        try:
            minio_endpoint = self.config.get("minio_endpoint")
            minio_access_key = self.config.get("minio_access_key")
            minio_secret_key = self.config.get("minio_secret_key")
            minio_secure = self.config.get("minio_secure", False)
            self.minio_bucket_name = self.config.get("minio_bucket_name")

            self.minio_client = MinioClient(
                endpoint=minio_endpoint,
                access_key=minio_access_key,
                secret_key=minio_secret_key,
                secure=minio_secure
            )
            self.minio_client.connect()
            self.minio_client.ensure_bucket_exists(self.minio_bucket_name)
            logger.info(f"MinIO 已连接，Bucket '{self.minio_bucket_name}' 已就绪。")

        except Exception as e:
            logger.error(f"MinIO 初始化失败: {e}", exc_info=True)
            return

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """监听所有消息，并将其分发给逻辑处理器。"""
        if not self.db_session or not self.minio_client:
            logger.warning("数据库或 MinIO 未初始化，跳过消息记录。")
            return
        
        logic.handle_message_event(
            event=event,
            session=self.db_session,
            minio_client=self.minio_client,
            bucket_name=self.minio_bucket_name,
            db_engine=self.db_engine
        )

    async def terminate(self):
        """销毁插件，关闭数据库连接。"""
        logger.info("正在终止 Message Logger 插件...")
        if self.db_session:
            self.db_session.close()
            logger.info("数据库会话已关闭。")
