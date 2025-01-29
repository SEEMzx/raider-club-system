# Raider Club System

一个基于 **Flask** 的游戏战队管理系统，用于高效管理战队成员、记录对战数据并生成排行榜。

---

## ✨ 功能特点

- **用户管理**：支持管理员、队长、成员等角色权限管理。
- **战队管理**：可创建、加入或退出战队，管理队员信息。
- **战绩系统**：支持对战记录提交、审核与战绩截图上传。
- **实时排行榜**：包括个人 KD 和团队统计数据。
- **数据可视化**：提供战绩统计的图形化展示。

---

## 📦 安装与运行

以下是从克隆项目到成功运行的完整操作步骤：

### 1. 克隆项目到本地
首先，从远程仓库克隆项目到本地：
```bash
git clone https://github.com/SEEMzx/raider-club-system.git
cd raider-club-system
```

### 2. 创建并激活虚拟环境
创建虚拟环境以隔离项目依赖：
```bash
python -m venv venv
```

激活虚拟环境：
- **Linux/Mac**:
  ```bash
  source venv/bin/activate
  ```
- **Windows**:
  ```bash
  .\venv\Scripts\activate
  ```

### 3. 安装项目依赖
在虚拟环境中运行以下命令，安装所需依赖：
```bash
pip install -r requirements.txt
```

### 4. 初始化数据库
运行数据库迁移脚本以初始化 SQLite 数据库：
```bash
python migrate_db.py
```

### 5. 启动应用
启动 Flask 应用程序：
```bash
python app.py
```

默认情况下，系统将在本地 `http://localhost:5001` 运行。

---

## 👥 系统角色

- **管理员 (Admin)**：全局权限管理，可操作所有用户和战队。
- **队长 (Leader)**：负责管理所属战队成员，并审核战绩。
- **成员 (Member)**：提交战绩并查看排行榜。

---

## 🔍 功能模块

### 用户管理
- 用户注册与登录
- 个人资料编辑
- 权限分级控制

### 战队管理
- 战队创建与解散
- 队员管理
- 查看战队统计数据

### 战绩系统
- 对战记录提交与审核
- 上传战绩截图
- KD 数据统计与可视化

### 排行榜
- 实时个人 KD 排行
- 团队胜率排行
- 支持筛选与过滤

---

## 📁 项目目录结构

项目的主要文件和目录结构如下：

```plaintext
raider-club-system/
├── app.py             # 主应用程序入口
├── migrate_db.py      # 数据库迁移脚本
├── requirements.txt   # 项目依赖清单
├── static/            # 静态文件
│   ├── css/           # 样式表
│   └── uploads/       # 战绩截图存储
├── templates/         # HTML 模板文件
└── instance/          # 数据库文件存储
```
