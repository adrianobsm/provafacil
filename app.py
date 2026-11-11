import csv, io, os, random, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from openpyxl import load_workbook
from werkzeug.security import check_password_hash, generate_password_hash

BASE=os.path.abspath(os.path.dirname(__file__))
DB=os.getenv('DATABASE_PATH',os.path.join(BASE,'dados','provafacil.db'))
app=Flask(__name__);app.secret_key=os.getenv('SECRET_KEY','troque-esta-chave')
app.config['MAX_CONTENT_LENGTH']=8*1024*1024
COLS=['Assunto','Enunciado','AlternativaA','AlternativaB','AlternativaC','AlternativaD','AlternativaCorreta','Justificativa']

def con():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def now():return datetime.now().strftime('%d/%m/%Y %H:%M')
def init_db():
 os.makedirs(os.path.dirname(DB),exist_ok=True)
 with con() as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,login TEXT UNIQUE NOT NULL,password TEXT NOT NULL,admin INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT NOT NULL,statement TEXT NOT NULL,a TEXT NOT NULL,b TEXT NOT NULL,c TEXT NOT NULL,d TEXT NOT NULL,correct TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(subject,statement));
  CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,subject TEXT NOT NULL,total INTEGER NOT NULL,minimum INTEGER NOT NULL,owner INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL,FOREIGN KEY(owner) REFERENCES users(id));
  CREATE TABLE IF NOT EXISTS exam_questions(exam INTEGER NOT NULL,question INTEGER NOT NULL,position INTEGER NOT NULL,PRIMARY KEY(exam,question),FOREIGN KEY(exam) REFERENCES exams(id) ON DELETE CASCADE,FOREIGN KEY(question) REFERENCES questions(id));
  CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,exam INTEGER NOT NULL,user INTEGER NOT NULL,hits INTEGER NOT NULL,total INTEGER NOT NULL,passed INTEGER NOT NULL,created TEXT NOT NULL,FOREIGN KEY(exam) REFERENCES exams(id),FOREIGN KEY(user) REFERENCES users(id));
  CREATE TABLE IF NOT EXISTS answers(id INTEGER PRIMARY KEY AUTOINCREMENT,attempt INTEGER NOT NULL,question INTEGER NOT NULL,answer TEXT,hit INTEGER NOT NULL,FOREIGN KEY(attempt) REFERENCES attempts(id) ON DELETE CASCADE,FOREIGN KEY(question) REFERENCES questions(id));
  ''')
  if not c.execute('SELECT 1 FROM users WHERE admin=1').fetchone():c.execute('INSERT INTO users(name,login,password,admin,active,created) VALUES(?,?,?,?,?,?)',('Administrador','admin',generate_password_hash(os.getenv('ADMIN_PASSWORD','admin123')),1,1,now()))
def me():
 if not session.get('uid'):return None
 with con() as c:return c.execute('SELECT id,name,login,admin,active FROM users WHERE id=?',(session['uid'],)).fetchone()
@app.context_processor
def context():return {'u':me()}
def auth(admin=False):
 def deco(fn):
  @wraps(fn)
  def wrapped(*a,**k):
   u=me()
   if not u or not u['active']:session.clear();flash('Entre para continuar.','error');return redirect(url_for('login'))
   if admin and not u['admin']:abort(403)
   return fn(*a,**k)
  return wrapped
 return deco

def exam_data(eid):
 with con() as c:
  e=c.execute('SELECT e.*,u.name owner_name FROM exams e JOIN users u ON u.id=e.owner WHERE e.id=?',(eid,)).fetchone()
  qs=c.execute('SELECT q.*,x.position FROM exam_questions x JOIN questions q ON q.id=x.question WHERE x.exam=? ORDER BY x.position',(eid,)).fetchall()
 return e,qs

@app.route('/',methods=['GET'])
def home():
 if not me():return render_template('welcome.html')
 with con() as c:
  exams=c.execute('SELECT e.*,u.name owner_name FROM exams e JOIN users u ON u.id=e.owner WHERE e.active=1 ORDER BY e.id DESC').fetchall()
  subjects=c.execute('SELECT subject,COUNT(*) qty FROM questions GROUP BY subject ORDER BY subject').fetchall()
  history=c.execute('SELECT a.*,e.title FROM attempts a JOIN exams e ON e.id=a.exam WHERE a.user=? ORDER BY a.id DESC',(me()['id'],)).fetchall()
 return render_template('home.html',exams=exams,subjects=subjects,history=history)
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with con() as c:user=c.execute('SELECT * FROM users WHERE login=?',(request.form['login'].strip().lower(),)).fetchone()
  if user and user['active'] and check_password_hash(user['password'],request.form['password']):session.clear();session['uid']=user['id'];return redirect(url_for('home'))
  flash('Usuário ou senha inválidos, ou usuário desativado.','error')
 return render_template('login.html')
@app.route('/register',methods=['GET','POST'])
def register():
 if me(): return redirect(url_for('home'))
 if request.method=='POST':
  name=request.form.get('name','').strip()
  login_name=request.form.get('login','').strip().lower()
  password=request.form.get('password','')
  confirmation=request.form.get('confirmation','')
  if len(name)<2: flash('Informe um nome válido.','error')
  elif len(login_name)<3: flash('O usuário deve ter pelo menos 3 caracteres.','error')
  elif len(password)<6: flash('A senha deve ter pelo menos 6 caracteres.','error')
  elif password!=confirmation: flash('A confirmação da senha não confere.','error')
  else:
   try:
    with con() as c:
     c.execute('INSERT INTO users(name,login,password,admin,active,created) VALUES(?,?,?,?,?,?)',(name,login_name,generate_password_hash(password),0,1,now()))
    flash('Cadastro realizado. Agora você já pode entrar.','success')
    return redirect(url_for('login'))
   except sqlite3.IntegrityError: flash('Esse nome de usuário já está cadastrado.','error')
 return render_template('register.html')

@app.get('/logout')
def logout():session.clear();return redirect(url_for('home'))

@app.post('/exams')
@auth()
def create_exam():
 try:total=int(request.form['total']);minimum=int(request.form['minimum'])
 except ValueError:flash('Quantidades inválidas.','error');return redirect(url_for('home'))
 subject=request.form['subject'];title=request.form['title'].strip()
 with con() as c:ids=[r['id'] for r in c.execute('SELECT id FROM questions WHERE subject=?',(subject,))]
 if not title or total<1 or minimum not in range(1,total+1) or total>len(ids):flash(f'Configuração inválida. Existem {len(ids)} questões em {subject}.','error');return redirect(url_for('home'))
 random.shuffle(ids)
 with con() as c:
  cur=c.execute('INSERT INTO exams(title,subject,total,minimum,owner,active,created) VALUES(?,?,?,?,?,?,?)',(title,subject,total,minimum,me()['id'],1,now()));eid=cur.lastrowid
  c.executemany('INSERT INTO exam_questions(exam,question,position) VALUES(?,?,?)',[(eid,q,i+1) for i,q in enumerate(ids[:total])])
 flash('Prova criada e publicada.','success');return redirect(url_for('home'))
@app.get('/exams/<int:eid>')
@auth()
def take_exam(eid):
 e,qs=exam_data(eid)
 if not e or not e['active']:abort(404)
 return render_template('exam.html',e=e,qs=qs)
@app.post('/exams/<int:eid>/finish')
@auth()
def finish_exam(eid):
 e,qs=exam_data(eid)
 if not e:abort(404)
 replies=[];hits=0
 for q in qs:
  answer=request.form.get(f'q{q["id"]}','');hit=answer==q['correct'];hits+=int(hit);replies.append((q['id'],answer,int(hit)))
 passed=hits>=e['minimum']
 with con() as c:
  cur=c.execute('INSERT INTO attempts(exam,user,hits,total,passed,created) VALUES(?,?,?,?,?,?)',(eid,me()['id'],hits,e['total'],int(passed),now()));aid=cur.lastrowid
  c.executemany('INSERT INTO answers(attempt,question,answer,hit) VALUES(?,?,?,?)',[(aid,*r) for r in replies])
 return redirect(url_for('attempt_detail',aid=aid))
@app.get('/attempts/<int:aid>')
@auth()
def attempt_detail(aid):
 with con() as c:
  attempt=c.execute('SELECT a.*,e.title,e.subject,e.minimum,u.name owner_name FROM attempts a JOIN exams e ON e.id=a.exam JOIN users u ON u.id=e.owner WHERE a.id=? AND a.user=?',(aid,me()['id'])).fetchone()
  if not attempt:abort(404)
  rows=c.execute('SELECT x.answer,x.hit,q.* FROM answers x JOIN questions q ON q.id=x.question WHERE x.attempt=? ORDER BY x.id',(aid,)).fetchall()
 fields={'A':'a','B':'b','C':'c','D':'d'}
 details=[{'row':r,'marked':r[fields[r['answer']]] if r['answer'] in fields else 'Não respondida','right':r[fields[r['correct']]]} for r in rows]
 return render_template('attempt.html',attempt=attempt,details=details)
@app.get('/exams/<int:eid>/print')
@auth()
def print_exam(eid):
 e,qs=exam_data(eid)
 if not e:abort(404)
 return render_template('print_exam.html',e=e,qs=qs,key=False)
@app.get('/exams/<int:eid>/answer-key')
@auth(admin=True)
def print_key(eid):
 e,qs=exam_data(eid)
 if not e:abort(404)
 return render_template('print_exam.html',e=e,qs=qs,key=True)

@app.route('/admin/users')
@auth(admin=True)
def users():
 with con() as c:rows=c.execute('SELECT * FROM users ORDER BY name').fetchall()
 return render_template('users.html',rows=rows)
@app.route('/admin/users/new',methods=['GET','POST'])
@auth(admin=True)
def user_new():
 if request.method=='POST':
  try:
   with con() as c:c.execute('INSERT INTO users(name,login,password,admin,active,created) VALUES(?,?,?,?,?,?)',(request.form['name'].strip(),request.form['login'].strip().lower(),generate_password_hash(request.form['password']),int('admin' in request.form),1,now()))
   flash('Usuário criado.','success');return redirect(url_for('users'))
  except sqlite3.IntegrityError:flash('Login já cadastrado.','error')
 return render_template('user_form.html',row=None)
@app.route('/admin/users/<int:uid>/edit',methods=['GET','POST'])
@auth(admin=True)
def user_edit(uid):
 with con() as c:row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
 if not row:abort(404)
 if request.method=='POST':
  if uid==me()['id'] and 'active' not in request.form:flash('Você não pode desativar sua própria conta.','error');return redirect(url_for('users'))
  with con() as c:c.execute('UPDATE users SET name=?,login=?,admin=?,active=? WHERE id=?',(request.form['name'].strip(),request.form['login'].strip().lower(),int('admin' in request.form),int('active' in request.form),uid))
  flash('Usuário atualizado.','success');return redirect(url_for('users'))
 return render_template('user_form.html',row=row)
@app.post('/admin/users/<int:uid>/password')
@auth(admin=True)
def user_password(uid):
 password=request.form['password']
 if len(password)<6:flash('A senha deve ter pelo menos 6 caracteres.','error')
 else:
  with con() as c:c.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password),uid))
  flash('Senha redefinida.','success')
 return redirect(url_for('users'))
@app.post('/admin/users/<int:uid>/delete')
@auth(admin=True)
def user_delete(uid):
 if uid==me()['id']:flash('Você não pode excluir sua própria conta.','error');return redirect(url_for('users'))
 try:
  with con() as c:c.execute('DELETE FROM users WHERE id=?',(uid,))
  flash('Usuário excluído.','success')
 except sqlite3.IntegrityError:flash('O usuário possui provas ou tentativas. Desative-o em vez de excluir.','error')
 return redirect(url_for('users'))

@app.route('/admin/questions')
@auth(admin=True)
def questions():
 search=request.args.get('search','');subject=request.args.get('subject','')
 sql='SELECT * FROM questions WHERE (statement LIKE ? OR subject LIKE ?)';args=['%'+search+'%','%'+search+'%']
 if subject:sql+=' AND subject=?';args.append(subject)
 sql+=' ORDER BY subject,id'
 with con() as c:rows=c.execute(sql,args).fetchall();subjects=c.execute('SELECT subject,COUNT(*) qty FROM questions GROUP BY subject ORDER BY subject').fetchall()
 return render_template('questions.html',rows=rows,subjects=subjects,search=search,subject=subject)
@app.route('/admin/questions/new',methods=['GET','POST'])
@app.route('/admin/questions/<int:qid>/edit',methods=['GET','POST'])
@auth(admin=True)
def question_form(qid=None):
 row=None
 if qid:
  with con() as c:row=c.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()
  if not row:abort(404)
 if request.method=='POST':
  values=(request.form['subject'].strip(),request.form['statement'].strip(),request.form['a'].strip(),request.form['b'].strip(),request.form['c'].strip(),request.form['d'].strip(),request.form['correct'],request.form['reason'].strip())
  try:
   with con() as c:
    if qid:c.execute('UPDATE questions SET subject=?,statement=?,a=?,b=?,c=?,d=?,correct=?,reason=? WHERE id=?',(*values,qid))
    else:c.execute('INSERT INTO questions(subject,statement,a,b,c,d,correct,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',(*values,now()))
   flash('Questão salva.','success');return redirect(url_for('questions'))
  except sqlite3.IntegrityError:flash('Já existe questão com o mesmo assunto e enunciado.','error')
 return render_template('question_form.html',row=row)
@app.post('/admin/questions/<int:qid>/duplicate')
@auth(admin=True)
def question_duplicate(qid):
 with con() as c:r=c.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()
 if not r:abort(404)
 suffix=' (cópia)'
 with con() as c:c.execute('INSERT INTO questions(subject,statement,a,b,c,d,correct,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',(r['subject'],r['statement']+suffix,r['a'],r['b'],r['c'],r['d'],r['correct'],r['reason'],now()))
 flash('Questão duplicada.','success');return redirect(url_for('questions'))
@app.post('/admin/questions/<int:qid>/delete')
@auth(admin=True)
def question_delete(qid):
 try:
  with con() as c:c.execute('DELETE FROM questions WHERE id=?',(qid,))
  flash('Questão excluída.','success')
 except sqlite3.IntegrityError:flash('Questão usada em uma prova. Mantenha-a para preservar o histórico.','error')
 return redirect(url_for('questions'))
@app.post('/admin/questions/import')
@auth(admin=True)
def question_import():
 f=request.files.get('file')
 try:
  ext=os.path.splitext(f.filename)[1].lower()
  if ext=='.xlsx':data=list(load_workbook(f,read_only=True,data_only=True).active.values);rows=[dict(zip(data[0],r)) for r in data[1:]]
  elif ext in ('.csv','.txt'):
   text=f.read().decode('utf-8-sig');sep=csv.Sniffer().sniff(text[:2048],delimiters='|;,\t').delimiter;rows=list(csv.DictReader(io.StringIO(text),delimiter=sep))
  else:raise ValueError('Use XLSX, CSV ou TXT.')
  ok=bad=dup=0
  with con() as c:
   for raw in rows:
    r={str(k).strip():'' if v is None else str(v).strip() for k,v in raw.items()};correct=r.get('AlternativaCorreta','').upper()
    if any(not r.get(x) for x in COLS) or correct not in 'ABCD':bad+=1;continue
    try:c.execute('INSERT INTO questions(subject,statement,a,b,c,d,correct,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',(r['Assunto'],r['Enunciado'],r['AlternativaA'],r['AlternativaB'],r['AlternativaC'],r['AlternativaD'],correct,r['Justificativa'],now()));ok+=1
    except sqlite3.IntegrityError:dup+=1
  flash(f'{ok} importadas, {dup} duplicadas e {bad} inválidas.','success')
 except Exception as ex:flash(f'Falha na importação: {ex}','error')
 return redirect(url_for('questions'))

@app.get('/admin/exams')
@auth(admin=True)
def admin_exams():
 with con() as c:rows=c.execute('''SELECT e.*,u.name owner_name,COUNT(a.id) attempts,COUNT(DISTINCT a.user) people,ROUND(AVG(a.hits),2) average,ROUND(AVG(a.hits*100.0/a.total),1) percentage,ROUND(100.0*SUM(CASE WHEN a.passed=1 THEN 1 ELSE 0 END)/NULLIF(COUNT(a.id),0),1) approval FROM exams e JOIN users u ON u.id=e.owner LEFT JOIN attempts a ON a.exam=e.id GROUP BY e.id ORDER BY e.id DESC''').fetchall()
 return render_template('admin_exams.html',rows=rows)
@app.post('/admin/exams/<int:eid>/toggle')
@auth(admin=True)
def exam_toggle(eid):
 with con() as c:c.execute('UPDATE exams SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(eid,))
 return redirect(url_for('admin_exams'))
@app.get('/admin/backup')
@auth(admin=True)
def backup():
 with con() as c:c.execute('PRAGMA wal_checkpoint(FULL)')
 return send_file(DB,as_attachment=True,download_name=f'provafacil_backup_{datetime.now():%Y%m%d_%H%M}.db')

@app.errorhandler(403)
def forbidden(_):return render_template('error.html',title='Acesso negado',message='Esta área é exclusiva do administrador.'),403
init_db()
if __name__=='__main__':app.run(host='0.0.0.0',port=5000,debug=os.getenv('FLASK_DEBUG')=='1')
