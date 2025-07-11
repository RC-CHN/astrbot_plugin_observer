from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.mysql import JSON as MySQLJSON

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    message_id = Column(String(255), unique=True, index=True)
    session_id = Column(String(255), index=True)
    sender_id = Column(String(255), index=True)
    timestamp = Column(Integer, index=True)
    
    # 使用 dialect-specific JSON 类型
    raw_message_obj = Column(Text)  # Fallback for SQLite
    
    components = relationship("MessageComponent", back_populates="message", cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_on': 'raw_message_obj'
    }
    __table_args__ = (
        Index('idx_messages_timestamp', 'timestamp'),
    )

class MessageWithPGJSON(Message):
    __mapper_args__ = {'polymorphic_identity': 'postgresql'}
    raw_message_obj = Column(JSONB)

class MessageWithMySQLJSON(Message):
    __mapper_args__ = {'polymorphic_identity': 'mysql'}
    raw_message_obj = Column(MySQLJSON)


class MessageComponent(Base):
    __tablename__ = 'message_components'
    id = Column(Integer, primary_key=True)
    message_fk = Column(Integer, ForeignKey('messages.id', ondelete='CASCADE'), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    component_type = Column(String(50))
    component_data = Column(Text) # Storing as JSON string

    message = relationship("Message", back_populates="components")
    file = relationship("File", back_populates="component", uselist=False, cascade="all, delete-orphan")


class File(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    component_fk = Column(Integer, ForeignKey('message_components.id', ondelete='CASCADE'), nullable=False, unique=True)
    file_name = Column(String(255))
    minio_path = Column(String(1024))
    upload_timestamp = Column(Integer)

    component = relationship("MessageComponent", back_populates="file")


def get_engine(db_uri: str):
    """根据提供的 URI 创建 SQLAlchemy 引擎"""
    return create_engine(db_uri)

def init_db(engine):
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(engine)

def get_session(engine):
    """创建并返回一个新的数据库会话"""
    Session = sessionmaker(bind=engine)
    return Session()
