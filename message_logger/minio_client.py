from minio import Minio
from minio.error import S3Error
from urllib.parse import urlparse
import io

class MinioClient:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool = True):
        # 解析 endpoint 以去除 scheme (http/https)
        parsed_endpoint = urlparse(endpoint)
        self.endpoint = parsed_endpoint.netloc or parsed_endpoint.path

        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.client = None

    def connect(self):
        """初始化 MinIO 客户端"""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
        except (TypeError, S3Error) as e:
            # 可以在这里添加更详细的日志记录
            raise ConnectionError(f"无法连接到 MinIO: {e}") from e

    def ensure_bucket_exists(self, bucket_name: str):
        """确保指定的 bucket 存在，如果不存在则创建"""
        if not self.client:
            raise ConnectionError("MinIO 客户端未初始化，请先调用 connect() 方法。")
        
        try:
            found = self.client.bucket_exists(bucket_name)
            if not found:
                self.client.make_bucket(bucket_name)
        except S3Error as e:
            raise IOError(f"检查或创建 bucket '{bucket_name}' 时出错: {e}") from e

    def upload_file(self, bucket_name: str, object_name: str, data: io.BytesIO, length: int):
        """将内存中的二进制数据上传到 MinIO"""
        if not self.client:
            raise ConnectionError("MinIO 客户端未初始化，请先调用 connect() 方法。")

        try:
            self.client.put_object(
                bucket_name,
                object_name,
                data,
                length=length,
                content_type='application/octet-stream'
            )
        except S3Error as e:
            raise IOError(f"上传文件到 '{bucket_name}/{object_name}' 时出错: {e}") from e
