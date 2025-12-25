# 飞书AI聊天机器人

基于GitHub部署的飞书AI聊天机器人，支持与DeepSeek等AI服务集成。

## 功能特点
- ✅ 飞书消息接收与回复
- ✅ 集成DeepSeek AI
- ✅ 支持私聊和群聊
- ✅ 命令系统
- ✅ 健康检查

## 快速开始

### 1. 部署到Railway（推荐）
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template)

### 2. 本地运行
```bash
# 克隆仓库
git clone https://github.com/rongwei1978/feishu-ai-bot.git
cd feishu-ai-bot

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入你的密钥

# 运行应用
python app.py
