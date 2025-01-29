#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from datetime import datetime
from app import app, db, Team, User, Checkin

def backup_database():
    """备份现有数据库"""
    if os.path.exists('instance/raider.db'):
        backup_dir = 'database_backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'raider_{timestamp}.db')
        
        try:
            shutil.copy2('instance/raider.db', backup_path)
            print(f"数据库已备份至: {backup_path}")
            return True
        except Exception as e:
            print(f"备份数据库失败: {str(e)}")
            return False
    return True

def create_default_teams():
    """创建默认团队"""
    teams = [
        {'name': '一队', 'type': 'vehicle'},
        {'name': '二队', 'type': 'infantry'},
        {'name': '三队', 'type': 'vehicle'},
    ]
    
    for team_data in teams:
        team = Team(name=team_data['name'])
        db.session.add(team)
    db.session.commit()
    print("默认团队创建完成")

def create_admin_user():
    """创建管理员账号"""
    try:
        admin = User(username='管理员', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("管理员账号创建成功")
        print("用户名: 管理员")
        print("密码: admin123")
    except Exception as e:
        print(f"创建管理员账号失败: {str(e)}")
        db.session.rollback()
        raise

def reset_database():
    """重置数据库"""
    try:
        # 备份现有数据库
        if not backup_database():
            if input("备份失败，是否继续? (y/N): ").lower() != 'y':
                print("操作已取消")
                return False

        print("开始重置数据库...")
        
        # 在应用上下文中执行操作
        with app.app_context():
            # 删除所有表
            db.drop_all()
            print("已删除所有表")
            
            # 创建所有表
            db.create_all()
            print("已创建新表结构")
            
            # 创建默认数据
            create_default_teams()
            create_admin_user()
            
            print("\n数据库重置完成！")
            return True
            
    except Exception as e:
        print(f"重置数据库时发生错误: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        reset_database()
    else:
        print("警告: 此操作将删除所有现有数据！")
        print("数据库将被备份到 database_backups 目录")
        if input("是否继续? (y/N): ").lower() == 'y':
            reset_database()
        else:
            print("操作已取消")
