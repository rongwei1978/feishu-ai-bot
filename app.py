#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书AI聊天机器人 - 主程序
部署在GitHub上运行
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# ==================== 配置部分 ====================
# 这些值将从GitHub Secrets或环境变量中读取
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

# 存储飞书访问令牌（临时缓存）
feishu_token_cache = {
    'token': None,
    'expire_time': 0
}

# ==================== 工具函数 ====================
def get_feishu_access_token():
    """获取飞书访问令牌（2小时有效期）"""
    import time
    
    # 检查缓存是否有效
    current_time = time.time()
    if (feishu_token_cache['token'] and 
        current_time < feishu_token_cache['expire_time']):
        return feishu_token_cache['token']
    
    # 重新获取令牌
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        result = response.json()
        
        if result.get("code") == 0:
            token = result.get("tenant_access_token")
            # 缓存令牌，设置过期时间（提前5分钟过期）
            feishu_token_cache['token'] = token
            feishu_token_cache['expire_time'] = current_time + 6600  # 110分钟
            logger.info("飞书令牌获取成功")
            return token
        else:
            logger.error(f"飞书令牌获取失败: {result}")
            return None
    except Exception as e:
        logger.error(f"获取飞书令牌异常: {str(e)}")
        return None

def send_feishu_message(receive_id, content, msg_type="text"):
    """发送消息到飞书"""
    token = get_feishu_access_token()
    if not token:
        return {"code": -1, "msg": "获取飞书令牌失败"}
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 确定接收ID类型
    if receive_id.startswith("ou_"):
        receive_id_type = "open_id"
    elif receive_id.startswith("on_"):
        receive_id_type = "union_id"
    elif receive_id.startswith("oc_"):
        receive_id_type = "chat_id"
    else:
        receive_id_type = "user_id"
    
    # 构造消息内容
    if msg_type == "text":
        msg_content = {"text": content}
    else:
        msg_content = {"text": content}
    
    params = {"receive_id_type": receive_id_type}
    data = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": json.dumps(msg_content)
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"发送飞书消息失败: {str(e)}")
        return {"code": -1, "msg": str(e)}

def call_ai_api(user_message):
    """调用AI API（支持多种AI服务）"""
    # 优先使用DeepSeek
    if DEEPSEEK_API_KEY:
        return call_deepseek_api(user_message)
    
    # 如果没有配置API密钥，返回示例回复
    return "这是一个示例回复。请配置AI API密钥以获得真实回复。"

def call_deepseek_api(user_message):
    """调用DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        return "未配置DeepSeek API密钥"
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个有帮助的助手，请用中文回答。"},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 1000,
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return "AI返回格式异常"
        else:
            error_msg = f"DeepSeek API错误: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f", {error_detail}"
            except:
                error_msg += f", {response.text[:100]}"
            return error_msg
            
    except requests.exceptions.Timeout:
        return "AI服务响应超时，请稍后重试"
    except Exception as e:
        return f"AI服务异常: {str(e)}"

# ==================== 路由处理 ====================
@app.route('/')
def home():
    """首页"""
    return jsonify({
        "status": "running",
        "service": "Feishu AI Chat Bot",
        "version": "1.0.0",
        "endpoints": {
            "home": "/",
            "webhook": "/webhook (POST)",
            "health": "/health"
        }
    })

@app.route('/health')
def health_check():
    """健康检查"""
    return jsonify({"status": "healthy", "timestamp": get_current_time()})

@app.route('/webhook', methods=['POST'])
def webhook():
    """飞书事件订阅回调"""
    try:
        data = request.json
        logger.info(f"收到飞书事件: {json.dumps(data, ensure_ascii=False)[:200]}")
        
        # 1. URL验证请求
        if data.get("type") == "url_verification":
            challenge = data.get("challenge", "")
            logger.info(f"URL验证请求，challenge: {challenge}")
            return jsonify({"challenge": challenge})
        
        # 2. 事件回调
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            
            # 处理消息接收事件
            if event.get("type") == "im.message.receive_v1":
                message = event.get("message", {})
                message_type = message.get("message_type", "")
                
                # 只处理文本消息
                if message_type == "text":
                    # 解析消息内容
                    content = message.get("content", "{}")
                    try:
                        content_dict = json.loads(content)
                        user_text = content_dict.get("text", "").strip()
                    except:
                        user_text = content
                    
                    # 获取发送者信息
                    sender = event.get("sender", {})
                    sender_id = sender.get("sender_id", {})
                    user_id = sender_id.get("user_id", "")
                    
                    # 获取聊天信息
                    chat_id = message.get("chat_id", "")
                    chat_type = message.get("chat_type", "")
                    
                    # 确定回复对象
                    receive_id = user_id if chat_type == "p2p" else chat_id
                    
                    # 处理帮助命令
                    if user_text.lower() in ["/help", "帮助", "help"]:
                        reply = """🤖 飞书AI助手使用指南：

常用命令：
/help - 显示此帮助信息
/test - 测试机器人是否在线
/about - 关于机器人

直接对话：
直接向我提问，我会尽力回答！

技术支持：
如有问题，请检查配置或联系管理员。

当前状态：✅ 运行正常"""
                        send_feishu_message(receive_id, reply)
                        return jsonify({"code": 0, "msg": "help command"})
                    
                    # 处理测试命令
                    elif user_text.lower() in ["/test", "测试", "ping"]:
                        send_feishu_message(receive_id, "✅ 机器人连接正常！")
                        return jsonify({"code": 0, "msg": "test command"})
                    
                    # 处理关于命令
                    elif user_text.lower() in ["/about", "关于", "info"]:
                        reply = """📱 飞书AI助手
版本：1.0.0
功能：智能对话、问题解答
技术支持：GitHub部署
状态：运行中"""
                        send_feishu_message(receive_id, reply)
                        return jsonify({"code": 0, "msg": "about command"})
                    
                    # 处理普通对话
                    elif user_text:
                        logger.info(f"处理用户消息: {user_id} -> {user_text[:50]}...")
                        
                        # 调用AI API
                        ai_reply = call_ai_api(user_text)
                        
                        # 发送回复
                        send_result = send_feishu_message(receive_id, ai_reply)
                        logger.info(f"发送回复结果: {send_result}")
                        
                        return jsonify({"code": 0, "msg": "message processed"})
        
        return jsonify({"code": 0, "msg": "event received"})
        
    except Exception as e:
        logger.error(f"处理webhook异常: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": f"server error: {str(e)}"}), 500

def get_current_time():
    """获取当前时间字符串"""
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

# ==================== 启动应用 ====================
if __name__ == '__main__':
    # 从环境变量读取端口，默认为8080
    port = int(os.environ.get('PORT', 8080))
    
    # 检查必要配置
    if not DEEPSEEK_API_KEY:
        logger.warning("未设置DEEPSEEK_API_KEY，将使用示例回复")
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        logger.warning("飞书配置不完整，某些功能可能受限")
    
    logger.info(f"启动飞书AI机器人服务，端口: {port}")
    logger.info(f"飞书App ID: {FEISHU_APP_ID[:10]}...")
    logger.info(f"DeepSeek API Key: {DEEPSEEK_API_KEY[:10]}..." if DEEPSEEK_API_KEY else "DeepSeek API Key: 未设置")
    
    app.run(host='0.0.0.0', port=port, debug=False)
