import os

# 火山引擎配置（从环境变量读取）
AK = os.getenv('VOLC_AK', '')
SK = os.getenv('VOLC_SK', '')

# TOS配置
TOS_ENDPOINT = 'tos-cn-beijing.volces.com'
TOS_BUCKET = 'asas'
TOS_REGION = 'cn-beijing'

# 知识库配置
KB_DOMAIN = 'api-knowledgebase.mlp.cn-beijing.volces.com'
