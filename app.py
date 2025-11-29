# app.py

# --- Imports ---
import os
import io
import csv
from datetime import datetime
from flask import Flask, render_template, url_for, redirect, request, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from fpdf import FPDF
from sqlalchemy import desc

# --- App Configuration ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///college_admission.db'
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_changed'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    application = db.relationship('Application', backref='applicant', uselist=False)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(10), unique=True, nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=False)
    father_name = db.Column(db.String(100), nullable=True)
    mother_name = db.Column(db.String(100), nullable=True)
    previous_school = db.Column(db.String(150), nullable=True)
    marks_obtained = db.Column(db.Float, nullable=True)
    total_marks = db.Column(db.Float, nullable=True)
    marksheet_path = db.Column(db.String(200), nullable=True) # Changed to nullable for drafts
    photo_path = db.Column(db.String(200), nullable=True) # Changed to nullable for drafts
    signature_path = db.Column(db.String(200), nullable=True) # Changed to nullable for drafts
    community_cert_path = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='Pending')

    # --- MODIFIED/NEW COLUMNS FOR DRAFT & PAYMENT FEATURES ---
    payment_status = db.Column(db.String(20), default='Unpaid')
    is_draft = db.Column(db.Boolean, default=True)
    # --- END OF CHANGES ---

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True) # Changed to nullable for drafts
    course = db.relationship('Course')

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PDF(FPDF):
    def header(self):
        # College Logo (optional, place a logo in static folder)
        # self.image('static/logo.png', 10, 8, 33)
        self.set_font('Arial', 'B', 20)
        self.cell(0, 10, 'College Admission Portal', 0, 1, 'C')
        self.set_font('Arial', '', 12)
        self.cell(0, 10, 'Application Summary', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


# --- Helper function to create initial data ---
def create_initial_data():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(username='admin', email='admin@college.com', password=hashed_password, is_admin=True)
            db.session.add(admin)
            print("Admin user created with username 'admin' and password 'admin123'")
        if Course.query.count() == 0:
            courses = [
                Course(name='Computer Science', description='Study of computation and information.'),
                Course(name='Mechanical Engineering', description='Design, analysis, and manufacturing of mechanical systems.'),
                Course(name='Business Administration', description='Management of business operations.')
            ]
            db.session.bulk_save_objects(courses)
            print("Sample courses created.")
        db.session.commit()

def generate_app_id():
    last_app = Application.query.order_by(Application.id.desc()).first()
    last_id = last_app.id if last_app else 0
    new_id = last_id + 1
    # Format to a 4-digit number with leading zeros
    return f"APP{new_id:04d}"
# ==================================================
#                  PUBLIC ROUTES
# ==================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        new_message = ContactMessage(
            name=request.form.get('name'),
            email=request.form.get('email'),
            subject=request.form.get('subject'),
            message=request.form.get('message')
        )
        db.session.add(new_message)
        db.session.commit()
        flash('Thank you for your message! We will get back to you shortly.', 'success')
        return redirect(url_for('index'))
    return render_template('contact.html')

# ==================================================
#            AUTHENTICATION ROUTES
# ==================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard') if current_user.is_admin else url_for('student_dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and bcrypt.check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('student_dashboard'))
        else:
            flash('Login unsuccessful. Please check your username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email')
        existing_user = User.query.filter(User.id != current_user.id, (User.username == current_user.username) | (User.email == current_user.email)).first()
        if existing_user:
            flash('Username or email is already taken by another user.', 'danger')
            return redirect(url_for('profile'))
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

# ==================================================
#                  STUDENT ROUTES (UPDATED)
# ==================================================
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    application = Application.query.filter_by(user_id=current_user.id).first()
    return render_template('student_dashboard.html', application=application)

@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    if current_user.is_admin:
        flash('Admins cannot submit applications.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Check for existing FINAL application
    existing_final_app = Application.query.filter_by(user_id=current_user.id, is_draft=False).first()
    if existing_final_app:
        flash('You have already submitted your final application.', 'warning')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        # This part now only handles going to the preview page
        session['application_data'] = {
            'full_name': request.form.get('full_name'),
            'dob': request.form.get('dob'),
            'gender': request.form.get('gender'),
            'phone_number': request.form.get('phone_number'),
            'address': request.form.get('address'),
            'father_name': request.form.get('father_name'),
            'mother_name': request.form.get('mother_name'),
            'previous_school': request.form.get('previous_school'),
            'marks_obtained': request.form.get('marks_obtained'),
            'total_marks': request.form.get('total_marks'),
            'course_id': request.form.get('course')
        }
        
        upload_folder = os.path.join('static', 'uploads', str(current_user.id))
        os.makedirs(upload_folder, exist_ok=True)

        files_to_upload = {
            'marksheet': request.files['marksheet'],
            'photo': request.files['photo'],
            'signature': request.files['signature'],
            'community_cert': request.files.get('community_cert')
        }
        
        # Keep existing file paths from draft if a new file isn't uploaded
        draft = Application.query.filter_by(user_id=current_user.id).first()

        for key, file in files_to_upload.items():
            path_key = f'{key}_path'
            if file:
                filename = f"{key}_{file.filename}"
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                session['application_data'][path_key] = os.path.join(str(current_user.id), filename)
            elif draft and getattr(draft, path_key):
                 session['application_data'][path_key] = getattr(draft, path_key)

        return redirect(url_for('preview_application'))

    # GET Request: Load draft if it exists
    draft = Application.query.filter_by(user_id=current_user.id, is_draft=True).first()
    courses = Course.query.all()
    return render_template('apply.html', courses=courses, draft=draft)

@app.route('/save-draft', methods=['POST'])
@login_required
def save_draft():
    # Find if a draft already exists
    draft = Application.query.filter_by(user_id=current_user.id).first()
    if not draft:
        draft = Application(user_id=current_user.id, is_draft=True)
        db.session.add(draft)
    
    # Update fields from form
    draft.full_name = request.form.get('full_name')
    if request.form.get('dob'):
        draft.date_of_birth = datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date()
    draft.gender = request.form.get('gender')
    draft.phone_number = request.form.get('phone_number')
    draft.address = request.form.get('address')
    draft.father_name = request.form.get('father_name')
    draft.mother_name = request.form.get('mother_name')
    draft.previous_school = request.form.get('previous_school')
    draft.marks_obtained = float(request.form.get('marks_obtained')) if request.form.get('marks_obtained') else None
    draft.total_marks = float(request.form.get('total_marks')) if request.form.get('total_marks') else None
    draft.course_id = request.form.get('course')
    
    # Handle file uploads
    upload_folder = os.path.join('static', 'uploads', str(current_user.id))
    os.makedirs(upload_folder, exist_ok=True)
    files_to_upload = {'marksheet': request.files['marksheet'], 'photo': request.files['photo'], 'signature': request.files['signature'], 'community_cert': request.files.get('community_cert')}
    
    for key, file in files_to_upload.items():
        if file:
            filename = f"{key}_{file.filename}"
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            setattr(draft, f'{key}_path', os.path.join(str(current_user.id), filename))

    db.session.commit()
    flash('Your application has been saved as a draft.', 'info')
    return redirect(url_for('student_dashboard'))

@app.route('/preview-application')
@login_required
def preview_application():
    if 'application_data' not in session:
        flash('No application data to preview. Please fill out the form.', 'warning')
        return redirect(url_for('apply'))
    app_data = session['application_data']
    course = Course.query.get(app_data.get('course_id'))
    return render_template('preview_application.html', app_data=app_data, course=course)

@app.route('/submit-application', methods=['POST'])
@login_required  
def submit_application():
    if 'application_data' not in session:
        flash('Your session expired. Please apply again.', 'danger')
        return redirect(url_for('apply'))

    app_data = session.pop('application_data', None)
    
    # Check if a draft exists to update it, otherwise create a new application
    application = Application.query.filter_by(user_id=current_user.id).first()
    if not application:
        application = Application(user_id=current_user.id)
        db.session.add(application)
        
    # Update all fields from session data
    application.full_name=app_data['full_name']
    application.date_of_birth=datetime.strptime(app_data['dob'], '%Y-%m-%d').date()
    application.gender=app_data.get('gender')
    application.phone_number=app_data.get('phone_number')
    application.address=app_data['address']
    application.father_name=app_data.get('father_name')
    application.mother_name=app_data.get('mother_name')
    application.previous_school=app_data.get('previous_school')
    application.marks_obtained=float(app_data['marks_obtained']) if app_data.get('marks_obtained') else None
    application.total_marks=float(app_data['total_marks']) if app_data.get('total_marks') else None
    application.course_id=app_data['course_id']
    application.marksheet_path=app_data.get('marksheet_path')
    application.photo_path=app_data.get('photo_path')
    application.signature_path=app_data.get('signature_path')
    application.community_cert_path=app_data.get('community_cert_path')
    
    # This is the key change: Finalize the application
    application.is_draft = False
    application.payment_status = 'Unpaid' # Set payment status to Unpaid
    if not application.app_id:
        application.app_id = generate_app_id()
            
    db.session.commit()
    
    flash('Your application has been submitted successfully! Please proceed to payment.', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    application = Application.query.filter_by(user_id=current_user.id, is_draft=False).first()
    
    if not application or application.payment_status != 'Unpaid':
        flash('No pending payment found for your application.', 'warning')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        # This simulates a successful payment
        application.payment_status = 'Paid'
        db.session.commit()
        flash('Payment successful! Your application is now complete and under review.', 'success')
        return redirect(url_for('student_dashboard'))
        
    return render_template('payment.html')

@app.route('/download-pdf/<int:app_id>')
@login_required
def download_pdf(app_id):
    application = Application.query.get_or_404(app_id)
    if application.user_id != current_user.id and not current_user.is_admin:
        flash('You are not authorized to view this document.', 'danger')
        return redirect(url_for('student_dashboard'))

    pdf = PDF()
    pdf.add_page()
    
    # --- Applicant Photo ---
    if application.photo_path:
        photo_full_path = os.path.join('static', 'uploads', application.photo_path)
        if os.path.exists(photo_full_path):
            pdf.image(photo_full_path, x=150, y=30, w=40)

    # --- Application Details ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Application Details", ln=True, border='B')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Application ID:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.app_id, ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Applicant Name:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.full_name, ln=True)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Date of Birth:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.date_of_birth.strftime('%d %B, %Y'), ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Applied Course:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.course.name, ln=True)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Application Status:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.status, ln=True)

    pdf.ln(10)

    # --- Personal Information ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Personal Information", ln=True, border='B')
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Address:")
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 10, application.address)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Phone Number:")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, application.phone_number or 'N/A', ln=True)
    
    pdf_output = pdf.output(dest='S').encode('latin-1')
    return Response(pdf_output, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=application_{application.app_id}.pdf'})

# ==================================================
#                   ADMIN ROUTES
# ==================================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))

    query = Application.query.filter_by(is_draft=False, payment_status='Paid')

    search_app_id = request.args.get('app_id')
    filter_course = request.args.get('course')
    filter_status = request.args.get('status')

    if search_app_id:
        query = query.filter(Application.app_id.ilike(f'%{search_app_id}%'))
    if filter_course:
        query = query.filter(Application.course_id == filter_course)
    if filter_status:
        query = query.filter(Application.status == filter_status)

    applications = query.all()
    courses = Course.query.all() 

    return render_template('admin_dashboard.html', 
                           applications=applications, 
                           courses=courses,
                           search_app_id=search_app_id,
                           filter_course=filter_course,
                           filter_status=filter_status)

@app.route('/admin/application/view/<int:app_id>')
@login_required
def view_application_details(app_id):
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    application = Application.query.get_or_404(app_id)
    return render_template('admin_application_view.html', application=application)

@app.route('/admin/application/<int:app_id>/<action>')
@login_required
def update_application_status(app_id, action):
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    application = Application.query.get_or_404(app_id)
    if action == 'approve':
        application.status = 'Approved'
    elif action == 'reject':
        application.status = 'Rejected'
    db.session.commit()
    flash(f'Application for {application.full_name} has been {application.status}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/courses')
@login_required
def manage_courses():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    courses = Course.query.all()
    return render_template('manage_courses.html', courses=courses)

@app.route('/admin/course/add', methods=['GET', 'POST'])
@login_required
def add_course():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    if request.method == 'POST':
        new_course = Course(name=request.form.get('name'), description=request.form.get('description'))
        db.session.add(new_course)
        db.session.commit()
        flash('Course has been added successfully!', 'success')
        return redirect(url_for('manage_courses'))
    return render_template('course_form.html', title='Add New Course')

@app.route('/admin/course/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_course(id):
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    course = Course.query.get_or_404(id)
    if request.method == 'POST':
        course.name = request.form.get('name')
        course.description = request.form.get('description')
        db.session.commit()
        flash('Course has been updated successfully!', 'success')
        return redirect(url_for('manage_courses'))
    return render_template('course_form.html', title='Edit Course', course=course)

@app.route('/admin/course/delete/<int:id>', methods=['POST'])
@login_required
def delete_course(id):
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    course = Course.query.get_or_404(id)
    if Application.query.filter_by(course_id=id).first():
        flash('Cannot delete this course as students have applied for it.', 'danger')
        return redirect(url_for('manage_courses'))
    db.session.delete(course)
    db.session.commit()
    flash('Course has been deleted successfully.', 'success')
    return redirect(url_for('manage_courses'))

@app.route('/admin/messages')
@login_required
def admin_messages():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    messages = ContactMessage.query.order_by(desc(ContactMessage.timestamp)).all()
    return render_template('admin_messages.html', messages=messages)

@app.route('/admin/reporting')
@login_required
def admin_reporting():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    
    base_query = Application.query.filter_by(is_draft=False, payment_status='Paid')
    
    stats = {
        'total': base_query.count(),
        'pending': base_query.filter_by(status='Pending').count(),
        'approved': base_query.filter_by(status='Approved').count(),
        'rejected': base_query.filter_by(status='Rejected').count(),
        'by_course': db.session.query(Course.name, db.func.count(Application.id)).join(Application).filter(Application.is_draft==False, Application.payment_status=='Paid').group_by(Course.name).all()
    }
    return render_template('admin_reporting.html', stats=stats)

@app.route('/admin/export-csv')
@login_required
def export_csv():
    if not current_user.is_admin:
        return redirect(url_for('student_dashboard'))
    output = io.StringIO()
    writer = csv.writer(output)
    header = ['ID', 'Full Name', 'Email', 'DOB', 'Course', 'Status', 'Payment']
    writer.writerow(header)
    # Export only paid, non-draft applications
    for app in Application.query.filter_by(is_draft=False, payment_status='Paid').all():
        row = [
            app.id, app.full_name, app.applicant.email,
            app.date_of_birth.strftime('%Y-%m-%d'),
            app.course.name, app.status, app.payment_status
        ]
        writer.writerow(row)
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=applications_export.csv"})

# --- Main Execution ---
if __name__ == '__main__':
    create_initial_data()
    app.run(debug=True)