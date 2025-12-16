import json
import os
import re
import hashlib
import requests
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials
import tos
import config

#签名生成逻辑
def prepare_request(method, path, params=None, data=None, doseq=0):
    #创建request
    if params:
        for key in params:
            if (
                    isinstance(params[key], int)
                    or isinstance(params[key], float)
                    or isinstance(params[key], bool)
            ):
                params[key] = str(params[key])
            elif isinstance(params[key], list):
                if not doseq:
                    params[key] = ",".join(params[key])
    r = Request()
    r.set_shema("http")
    r.set_method(method)
    r.set_connection_timeout(10)
    r.set_socket_timeout(10)
    mheaders = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        # "Host": g_knowledge_base_domain,
        # "V-Account-Id": account_id,
    }
    r.set_headers(mheaders)
    if params:
        r.set_query(params)
    r.set_host(g_knowledge_base_domain)
    r.set_path(path)
    if data is not None:
        r.set_body(json.dumps(data))
    # 生成签名
    credentials = Credentials(ak, sk, "air", "cn-north-1")
    SignerV4.sign(r, credentials)
    return r

#创建知识库逻辑
def create():
    #创建知识库的请求方式
    method = "POST"
    #创建知识库的请求路径
    path = "/api/knowledge/collection/create"
    #创建知识库所需要的一些参数
    request_params = {
        "name": "lzm_test2",
        "data_type": "unstructured_data",
        "preprocessing": {
            "chunking_strategy":"custom_balance",
            "multi_modal":["image_ocr"]
        },
        "index": {
            "cpu_quota": 1,
            "embedding_model": "doubao-embedding-and-m3",
            "embedding_dimension": 2048,
            "quant": "int8",
            "index_type": "hnsw_hybrid"
        },
    }
    info_req = prepare_request(method=method, path=path, data=request_params)
    rsp = requests.request(
        method=info_req.method,
        url="https://{}{}".format(g_knowledge_base_domain, info_req.path),
        headers=info_req.headers,
        data=info_req.body
    )
    print(rsp.text)

def add_doc(collection_name, doc_id, doc_name, doc_type, url, project="default", meta=None):
    """上传文档到知识库"""
    method = "POST"
    path = "/api/knowledge/doc/add"
    request_params = {
        "collection_name": collection_name,
        "project": project,
        "add_type": "url",
        "doc_id": doc_id,
        "doc_name": doc_name,
        "doc_type": doc_type,
        "url": url
    }
    if meta:
        request_params["meta"] = meta
    
    info_req = prepare_request(method=method, path=path, data=request_params)
    rsp = requests.request(
        method=info_req.method,
        url="https://{}{}".format(g_knowledge_base_domain, info_req.path),
        headers=info_req.headers,
        data=info_req.body
    )
    print(rsp.text)
    return rsp.json()

class KnowledgeBaseUploader:
    """本地文件 -> TOS -> 知识库 上传器"""
    
    def __init__(self, ak, sk, tos_endpoint, tos_bucket, kb_domain="api-knowledgebase.mlp.cn-beijing.volces.com", tos_region="cn-beijing"):
        self.ak = ak
        self.sk = sk
        self.tos_endpoint = tos_endpoint
        self.tos_bucket = tos_bucket
        self.tos_region = tos_region
        self.kb_domain = kb_domain
        self.tos_client = tos.TosClientV2(ak, sk, tos_endpoint, tos_region)
    
    def upload_to_tos(self, local_path, tos_key=None):
        """上传本地文件到TOS，返回TOS路径"""
        if tos_key is None:
            tos_key = os.path.basename(local_path)
        self.tos_client.put_object_from_file(self.tos_bucket, tos_key, local_path)
        return f"{self.tos_bucket}/{tos_key}"
    
    def get_presigned_url(self, tos_key, expires=3600):
        """获取TOS预签名URL"""
        return self.tos_client.pre_signed_url(tos.HttpMethodType.Http_Method_Get, self.tos_bucket, tos_key, expires).signed_url
    
    def _prepare_request(self, method, path, data=None):
        r = Request()
        r.set_shema("http")
        r.set_method(method)
        r.set_connection_timeout(10)
        r.set_socket_timeout(10)
        r.set_headers({"Accept": "application/json", "Content-Type": "application/json"})
        r.set_host(self.kb_domain)
        r.set_path(path)
        if data:
            r.set_body(json.dumps(data))
        credentials = Credentials(self.ak, self.sk, "air", "cn-north-1")
        SignerV4.sign(r, credentials)
        return r
    
    def add_doc_by_tos(self, collection_name, tos_path, project="default"):
        """通过TOS路径添加文档到知识库"""
        request_params = {
            "collection_name": collection_name,
            "project": project,
            "add_type": "tos",
            "tos_path": tos_path
        }
        req = self._prepare_request("POST", "/api/knowledge/doc/add", request_params)
        rsp = requests.post(f"https://{self.kb_domain}{req.path}", headers=req.headers, data=req.body)
        return rsp.json()
    
    def add_doc_by_url(self, collection_name, doc_id, doc_name, doc_type, url, project="default", meta=None):
        """通过URL添加文档到知识库"""
        request_params = {
            "collection_name": collection_name,
            "project": project,
            "add_type": "url",
            "doc_id": doc_id,
            "doc_name": doc_name,
            "doc_type": doc_type,
            "url": url
        }
        if meta:
            request_params["meta"] = meta
        req = self._prepare_request("POST", "/api/knowledge/doc/add", request_params)
        rsp = requests.post(f"https://{self.kb_domain}{req.path}", headers=req.headers, data=req.body)
        return rsp.json()
    
    def upload_local_to_kb(self, local_path, collection_name, user_id, doc_id=None, project="default", extra_meta=None):
        """一键上传：本地文件 -> TOS -> 知识库（按用户标签存储）"""
        filename = os.path.basename(local_path)
        doc_type = os.path.splitext(filename)[1].lstrip('.')
        if doc_type == 'jpg':
            doc_type = 'jpeg'
        
        # 上传到TOS（按用户分目录）
        tos_key = f"{user_id}/{filename}"
        self.upload_to_tos(local_path, tos_key)
        
        # 获取预签名URL
        url = self.get_presigned_url(tos_key)
        
        # 构建用户标签meta
        meta = [
            {"field_name": "user_id", "field_type": "string", "field_value": user_id}
        ]
        if extra_meta:
            meta.extend(extra_meta)
        
        # 添加到知识库
        if doc_id is None:
            doc_id = f"doc_{user_id}_" + hashlib.md5(filename.encode()).hexdigest()[:12]
        return self.add_doc_by_url(collection_name, doc_id, filename, doc_type, url, project, meta)


if __name__ == "__main__":
    uploader = KnowledgeBaseUploader(
        ak=config.AK,
        sk=config.SK,
        tos_endpoint=config.TOS_ENDPOINT,
        tos_bucket=config.TOS_BUCKET
    )
    
    # 按用户上传文档到知识库
    result = uploader.upload_local_to_kb(
        local_path=r"C:\Users\yaobowen.ALIT\Downloads\20251208阶段性工作汇报.pdf",
        collection_name="lzm_test2",
        user_id="user_001"  # 用户标识
    )
    print(result)