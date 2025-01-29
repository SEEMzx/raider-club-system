from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# 队伍类型常量
TEAM_TYPE_VEHICLE = 'vehicle'
TEAM_TYPE_INFANTRY = 'infantry'
TEAM_TYPES = {
    TEAM_TYPE_VEHICLE: '载具队伍',
    TEAM_TYPE_INFANTRY: '步兵队伍'
}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'raider_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///raider.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship('User', backref='team', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10), unique=True, nullable=False)  # 增加长度限制到10
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='member')  # admin, manager, leader, member
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    total_kills = db.Column(db.Integer, default=0)
    total_deaths = db.Column(db.Integer, default=0)
    checkins = db.relationship('Checkin', foreign_keys='Checkin.user_id', backref='user', lazy=True)
    reviewed_checkins = db.relationship('Checkin', foreign_keys='Checkin.reviewed_by', backref='reviewer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def kd_ratio(self):
        if self.total_deaths == 0:
            return self.total_kills
        return round(self.total_kills / self.total_deaths, 2)
        
    def can_review_checkins(self):
        return self.role in ['admin', 'manager', 'leader']

    @property
    def is_admin(self):
        return self.role in ['admin', 'manager']
        
    @property
    def display_name(self):
        if self.team:
            return f"{self.team.name}·{self.username}"
        return self.username

class Checkin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    screenshot_path = db.Column(db.String(255))
    note = db.Column(db.Text)
    kills = db.Column(db.Integer, default=0)
    deaths = db.Column(db.Integer, default=0)
    team_type = db.Column(db.String(20), nullable=False)  # 'vehicle' 或 'infantry'
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    review_note = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    reviewed_at = db.Column(db.DateTime)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if len(username) != 2 or not all('\u4e00' <= char <= '\u9fff' for char in username):
            flash('昵称必须是两个汉字')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('该昵称已被使用')
            return redirect(url_for('register'))
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('注册成功')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"尝试登录: 用户名={username}")  # 调试信息
        
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"找到用户: ID={user.id}, 角色={user.role}")  # 调试信息
            if user.check_password(password):
                print("密码验证成功")  # 调试信息
                login_user(user)
                return redirect(url_for('index'))
            else:
                print("密码验证失败")  # 调试信息
        else:
            print("未找到用户")  # 调试信息
            
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin.html', users=users)

@app.route('/admin/teams', methods=['GET', 'POST'])
@login_required
def manage_teams():
    if not current_user.is_admin:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_team':
            team_name = request.form.get('team_name')
            if not team_name:
                flash('团队名称不能为空')
            else:
                team = Team(name=team_name)
                db.session.add(team)
                db.session.commit()
                flash('团队创建成功')
                
        elif action == 'delete_team':
            team_id = request.form.get('team_id')
            team = Team.query.get_or_404(team_id)
            # 将该团队的所有成员team_id设为None
            for member in team.members:
                member.team_id = None
                member.role = 'member'
            db.session.delete(team)
            db.session.commit()
            flash('团队删除成功')
            
    teams = Team.query.all()
    return render_template('manage_teams.html', teams=teams)

@app.route('/admin/users')
@login_required
def manage_users():
    if not current_user.is_admin:
        return redirect(url_for('index'))
        
    users = User.query.filter(User.id != current_user.id, User.role != 'admin').all()
    teams = Team.query.all()
    return render_template('manage_users.html', users=users, teams=teams)

@app.route('/admin/user/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': '无权限'}), 403
        
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    
    if action == 'update_team':
        team_id = request.form.get('team_id')
        role = request.form.get('role', 'member')
        
        if team_id:
            user.team_id = int(team_id)
            user.role = role
        else:
            user.team_id = None
            user.role = 'member'
            
        db.session.commit()
        return jsonify({'success': True})
        
    elif action == 'delete':
        if user.role == 'admin':
            return jsonify({'error': '不能删除管理员账号'}), 400
            
        # 删除用户的所有打卡记录
        Checkin.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
        
    return jsonify({'error': '无效的操作'}), 400

@app.route('/checkin_records')
@login_required
def checkin_records():
    if not current_user.can_review_checkins():
        return redirect(url_for('index'))
    
    # 获取所有打卡记录，按时间倒序排序
    latest_checkins = Checkin.query.order_by(Checkin.timestamp.desc()).all()
    
    # 获取用户统计信息
    users = User.query.filter(User.role != 'admin').all()
    user_stats = []
    
    for user in users:
        total_checkins = Checkin.query.filter_by(user_id=user.id).count()
        pending_checkins = Checkin.query.filter_by(user_id=user.id, status='pending').count()
        
        user_stats.append({
            'id': user.id,
            'username': user.display_name,
            'total_checkins': total_checkins,
            'pending_checkins': pending_checkins,
            'total_kills': user.total_kills,
            'total_deaths': user.total_deaths,
            'kd_ratio': user.kd_ratio
        })
    
    return render_template('checkin_records.html', 
                         latest_checkins=latest_checkins,
                         user_stats=user_stats,
                         TEAM_TYPE_VEHICLE=TEAM_TYPE_VEHICLE,
                         TEAM_TYPE_INFANTRY=TEAM_TYPE_INFANTRY,
                         TEAM_TYPES=TEAM_TYPES)

@app.route('/user_checkins/<int:user_id>')
@login_required
def user_checkins(user_id):
    if not current_user.can_review_checkins():
        return redirect(url_for('index'))
        
    user = User.query.get_or_404(user_id)
    checkins = Checkin.query.filter_by(user_id=user_id).order_by(Checkin.timestamp.desc()).all()
    
    return render_template('user_checkins.html', 
                         user=user,
                         checkins=checkins,
                         TEAM_TYPE_VEHICLE=TEAM_TYPE_VEHICLE,
                         TEAM_TYPE_INFANTRY=TEAM_TYPE_INFANTRY,
                         TEAM_TYPES=TEAM_TYPES)

@app.route('/review_checkin/<int:checkin_id>', methods=['POST'])
@login_required
def review_checkin(checkin_id):
    if not current_user.can_review_checkins():
        return jsonify({'error': '无权限'}), 403
        
    checkin = Checkin.query.get_or_404(checkin_id)
    
    # 如果是队长，检查是否是本团队成员的打卡记录
    if not current_user.is_admin and current_user.team_id != checkin.user.team_id:
        return jsonify({'error': '无权限审核其他团队成员的打卡记录'}), 403
        
    action = request.form.get('action')
    review_note = request.form.get('review_note', '')
    
    if action not in ['approve', 'reject', 're-review']:
        return jsonify({'error': '无效的操作'}), 400
        
    # 如果是重新审核，先恢复用户的击杀死亡数据
    if action == 're-review' and checkin.status == 'approved':
        user = checkin.user
        user.total_kills -= checkin.kills
        user.total_deaths -= checkin.deaths
        checkin.status = 'pending'
        checkin.review_note = ''
        checkin.reviewed_by = None
        checkin.reviewed_at = None
    else:
        checkin.status = 'approved' if action == 'approve' else 'rejected'
        checkin.review_note = review_note
        checkin.reviewed_by = current_user.id
        checkin.reviewed_at = datetime.utcnow()
        
        if action == 'approve':
            # 更新用户的击杀死亡数据
            user = checkin.user
            user.total_kills += checkin.kills
            user.total_deaths += checkin.deaths
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/leaderboard')
@login_required
def leaderboard():
    # 获取所有非管理员用户
    users = User.query.filter(User.role != 'admin').all()

    # 获取时间范围
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = now.replace(month=1, day=1)

    def get_stats_for_period(start_time=None, team_type=None):
        """获取指定时间段和队伍类型的统计数据"""
        stats = []
        for user in users:
            query = Checkin.query.filter(
                Checkin.user_id == user.id,
                Checkin.status == 'approved'
            )
            
            if start_time:
                query = query.filter(Checkin.timestamp >= start_time)
                
            if team_type:
                query = query.filter(Checkin.team_type == team_type)
                
            checkins = query.all()
            kills = sum(c.kills for c in checkins)
            deaths = sum(c.deaths for c in checkins)
            
            if kills > 0 or deaths > 0:
                stats.append({
                    'username': user.display_name,
                    'kills': kills,
                    'deaths': deaths,
                    'kd_ratio': round(kills / deaths, 2) if deaths > 0 else kills
                })
        return stats

    # 获取不同时间段和类型的统计数据
    periods = {
        'total': None,
        'year': year_start,
        'month': month_start,
        'week': week_start,
        'day': today_start
    }

    leaderboard_data = {}
    for period_name, start_time in periods.items():
        # 总击杀榜
        total_stats = get_stats_for_period(start_time)
        # 载具击杀榜
        vehicle_stats = get_stats_for_period(start_time, TEAM_TYPE_VEHICLE)
        # 步兵击杀榜
        infantry_stats = get_stats_for_period(start_time, TEAM_TYPE_INFANTRY)

        # 按击杀数排序
        leaderboard_data[period_name] = {
            'total': {
                'kills': sorted(total_stats, key=lambda x: x['kills'], reverse=True),
                'kd': sorted(total_stats, key=lambda x: x['kd_ratio'], reverse=True)
            },
            TEAM_TYPE_VEHICLE: {
                'kills': sorted(vehicle_stats, key=lambda x: x['kills'], reverse=True),
                'kd': sorted(vehicle_stats, key=lambda x: x['kd_ratio'], reverse=True)
            },
            TEAM_TYPE_INFANTRY: {
                'kills': sorted(infantry_stats, key=lambda x: x['kills'], reverse=True),
                'kd': sorted(infantry_stats, key=lambda x: x['kd_ratio'], reverse=True)
            }
        }

    return render_template('leaderboard.html',
                         leaderboard_data=leaderboard_data,
                         TEAM_TYPE_VEHICLE=TEAM_TYPE_VEHICLE,
                         TEAM_TYPE_INFANTRY=TEAM_TYPE_INFANTRY,
                         TEAM_TYPES=TEAM_TYPES)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_user.check_password(old_password):
                flash('当前密码错误')
                return redirect(url_for('profile'))
                
            if new_password != confirm_password:
                flash('新密码与确认密码不匹配')
                return redirect(url_for('profile'))
                
            current_user.set_password(new_password)
            db.session.commit()
            flash('密码修改成功')
            
        elif action == 'change_username':
            new_username = request.form.get('new_username')
            
            if len(new_username) != 2 or not all('\u4e00' <= char <= '\u9fff' for char in new_username):
                flash('昵称必须是两个汉字')
                return redirect(url_for('profile'))
                
            if User.query.filter_by(username=new_username).first() and new_username != current_user.username:
                flash('该昵称已被使用')
                return redirect(url_for('profile'))
                
            current_user.username = new_username
            db.session.commit()
            flash('昵称修改成功')
            
        return redirect(url_for('profile'))
    
    # 获取用户的签到记录
    checkins = Checkin.query.filter_by(user_id=current_user.id).order_by(Checkin.timestamp.desc()).all()
    
    # 计算总计数据
    total_stats = {
        'total': {'kills': 0, 'deaths': 0, 'kd': 0},
        TEAM_TYPE_VEHICLE: {'kills': 0, 'deaths': 0, 'kd': 0},
        TEAM_TYPE_INFANTRY: {'kills': 0, 'deaths': 0, 'kd': 0}
    }
    
    # 计算最近30天的数据
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_stats = {
        'total': {'kills': 0, 'deaths': 0, 'kd': 0},
        TEAM_TYPE_VEHICLE: {'kills': 0, 'deaths': 0, 'kd': 0},
        TEAM_TYPE_INFANTRY: {'kills': 0, 'deaths': 0, 'kd': 0}
    }
    
    # 计算每日数据趋势（最近7天）
    seven_days_ago = datetime.now() - timedelta(days=7)
    daily_stats = {
        'dates': [],
        'kills': [],
        'deaths': [],
        'kd': []
    }
    
    # 初始化最近7天的数据
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).date()
        daily_stats['dates'].insert(0, date.strftime('%m-%d'))
        daily_stats['kills'].insert(0, 0)
        daily_stats['deaths'].insert(0, 0)
        daily_stats['kd'].insert(0, 0)
    
    for checkin in checkins:
        if checkin.status == 'approved':
            # 更新总计数据
            total_stats['total']['kills'] += checkin.kills
            total_stats['total']['deaths'] += checkin.deaths
            total_stats[checkin.team_type]['kills'] += checkin.kills
            total_stats[checkin.team_type]['deaths'] += checkin.deaths
            
            # 更新最近30天数据
            if checkin.timestamp >= thirty_days_ago:
                recent_stats['total']['kills'] += checkin.kills
                recent_stats['total']['deaths'] += checkin.deaths
                recent_stats[checkin.team_type]['kills'] += checkin.kills
                recent_stats[checkin.team_type]['deaths'] += checkin.deaths
            
            # 更新每日数据趋势
            if checkin.timestamp >= seven_days_ago:
                day_index = (checkin.timestamp.date() - seven_days_ago.date()).days
                if 0 <= day_index < 7:
                    daily_stats['kills'][day_index] += checkin.kills
                    daily_stats['deaths'][day_index] += checkin.deaths
    
    # 计算KD比
    for stats in [total_stats, recent_stats]:
        for team_type in stats:
            kills = stats[team_type]['kills']
            deaths = stats[team_type]['deaths']
            stats[team_type]['kd'] = round(kills / deaths, 2) if deaths > 0 else kills
    
    # 计算每日KD比
    for i in range(7):
        kills = daily_stats['kills'][i]
        deaths = daily_stats['deaths'][i]
        daily_stats['kd'][i] = round(kills / deaths, 2) if deaths > 0 else kills

    return render_template('profile.html', 
                         user=current_user,
                         checkins=checkins,
                         total_stats=total_stats,
                         recent_stats=recent_stats,
                         daily_stats=daily_stats,
                         TEAM_TYPE_VEHICLE=TEAM_TYPE_VEHICLE,
                         TEAM_TYPE_INFANTRY=TEAM_TYPE_INFANTRY)

@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    if request.method == 'POST':
        team_type = request.form.get('team_type')
        if team_type not in TEAM_TYPES:
            flash('请选择正确的队伍类型')
            return redirect(url_for('checkin'))
            
        kills = int(request.form.get('kills', 0))
        deaths = int(request.form.get('deaths', 0))
        note = request.form.get('note', '')
        
        if 'screenshot' not in request.files:
            flash('请上传游戏截图')
            return redirect(url_for('checkin'))
            
        file = request.files['screenshot']
        if file.filename == '':
            flash('请选择文件')
            return redirect(url_for('checkin'))
            
        if file and allowed_file(file.filename):
            # 生成一个安全的文件名
            filename = f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            checkin = Checkin(
                user_id=current_user.id,
                screenshot_path=filename,
                kills=kills,
                deaths=deaths,
                note=note,
                team_type=team_type
            )
            db.session.add(checkin)
            db.session.commit()
            flash('打卡成功，等待审核')
            return redirect(url_for('checkin'))
        else:
            flash('不支持的文件格式')
            return redirect(url_for('checkin'))
    
    # 获取用户的打卡记录
    checkins = Checkin.query.filter_by(user_id=current_user.id).order_by(Checkin.timestamp.desc()).all()
    return render_template('checkin.html', checkins=checkins,
                         TEAM_TYPE_VEHICLE=TEAM_TYPE_VEHICLE,
                         TEAM_TYPE_INFANTRY=TEAM_TYPE_INFANTRY,
                         TEAM_TYPES=TEAM_TYPES)

@app.route('/team')
@login_required
def view_team():
    if not current_user.team_id:
        flash('你还没有加入任何团队')
        return redirect(url_for('index'))
    
    team = Team.query.get_or_404(current_user.team_id)
    return render_template('team.html', team=team)

@app.route('/team/member/<int:member_id>', methods=['POST'])
@login_required
def manage_team_member(member_id):
    if not current_user.team_id:
        return jsonify({'error': '你还没有加入任何团队'}), 403
        
    if current_user.role != 'leader':
        return jsonify({'error': '只有队长才能管理团队成员'}), 403
        
    member = User.query.get_or_404(member_id)
    if member.team_id != current_user.team_id:
        return jsonify({'error': '该成员不属于你的团队'}), 403
        
    action = request.form.get('action')
    
    if action == 'remove':
        member.team_id = None
        member.role = 'member'
        db.session.commit()
        return jsonify({'success': True})
        
    return jsonify({'error': '无效的操作'}), 400

@app.route('/team/<int:team_id>/remove_member/<int:user_id>', methods=['POST'])
@login_required
def remove_team_member(team_id, user_id):
    team = Team.query.get_or_404(team_id)
    user = User.query.get_or_404(user_id)
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        flash('你没有权限执行此操作')
        return redirect(url_for('index'))
        
    if current_user.role == 'leader' and current_user.team_id != team.id:
        flash('你只能管理自己的团队')
        return redirect(url_for('index'))
        
    if user in team.members:
        team.members.remove(user)
        user.team_id = None
        db.session.commit()
        flash(f'已将 {user.username} 移出团队')
        
    return jsonify({'error': '无效的操作'}), 400

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if 'change_username' in request.form:
            new_username = request.form.get('new_username')
            if new_username and new_username != current_user.username:
                current_user.username = new_username
                db.session.commit()
                flash('昵称修改成功')
        
        elif 'change_password' in request.form:
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not check_password_hash(current_user.password_hash, old_password):
                flash('原密码错误')
            elif new_password != confirm_password:
                flash('两次输入的新密码不一致')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('密码修改成功')
                
        return redirect(url_for('settings'))
        
    return render_template('settings.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 创建管理员账号（如果不存在）
        admin = User.query.filter_by(username="管理员").first()
        if not admin:
            admin = User(username="管理员", role='admin')
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    app.run(host='0.0.0.0', port=5001, debug=True)
