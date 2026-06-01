from dotenv import load_dotenv
load_dotenv()
from flask_dance.contrib.google import make_google_blueprint, google
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Produk, Keranjang, Order, Ulasan, Notifikasi, Alamat
from flask_migrate import Migrate
from functools import wraps
import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'rahasia123')
database_url = os.getenv('DATABASE_URL', 'sqlite:///marketplace.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

google_bp = make_google_blueprint(
    client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
    client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
    scope=[
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ],
    redirect_to='google_login_callback'
)
app.register_blueprint(google_bp, url_prefix='/login')

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

KATEGORI_LIST = ['Elektronik', 'Fashion', 'Makanan', 'Kesehatan', 'Olahraga', 'Rumah Tangga', 'Lainnya']
ONGKIR_PER_KOTA = {
    'Jakarta': 10000, 'Surabaya': 15000, 'Bandung': 12000,
    'Medan': 25000, 'Semarang': 13000, 'Yogyakarta': 13000,
    'Makassar': 30000, 'Palembang': 20000, 'Balikpapan': 35000, 'Denpasar': 20000,
}

def hitung_ongkir(kota):
    return ONGKIR_PER_KOTA.get(kota, 20000)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_notifikasi():
    if current_user.is_authenticated:
        notif = Notifikasi.query.filter_by(
            user_id=current_user.id, dibaca=False
        ).order_by(Notifikasi.tanggal.desc()).all()
        return dict(notifikasi_list=notif, notif_count=len(notif))
    return dict(notifikasi_list=[], notif_count=0)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Kamu tidak punya akses ke halaman ini!')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    kategori = request.args.get('kategori', '')
    if kategori:
        produk = Produk.query.filter_by(kategori=kategori).all()
    else:
        produk = Produk.query.all()
    return render_template('index.html', produk=produk, kategori_list=KATEGORI_LIST, kategori_aktif=kategori)

@app.route('/search')
def search():
    kata = request.args.get('q', '')
    produk = Produk.query.filter(Produk.nama.ilike(f'%{kata}%')).all()
    return render_template('index.html', produk=produk, kategori_list=KATEGORI_LIST, kategori_aktif='', kata=kata)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nama = request.form['nama']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        user_baru = User(nama=nama, email=email, password=password)
        db.session.add(user_baru)
        db.session.commit()
        flash('Registrasi berhasil! Silakan login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Email atau password salah!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/jual', methods=['GET', 'POST'])
@login_required
def jual():
    if request.method == 'POST':
        foto = request.files['foto']
        filename = secure_filename(foto.filename)
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        produk_baru = Produk(
            nama=request.form['nama'],
            harga=int(request.form['harga']),
            stok=int(request.form['stok']),
            deskripsi=request.form['deskripsi'],
            kategori=request.form['kategori'],
            foto=filename,
            user_id=current_user.id
        )
        db.session.add(produk_baru)
        db.session.commit()
        flash('Produk berhasil diupload!')
        return redirect(url_for('index'))
    return render_template('jual.html', kategori_list=KATEGORI_LIST)

@app.route('/produk/<int:produk_id>', methods=['GET', 'POST'])
def detail_produk(produk_id):
    produk = Produk.query.get_or_404(produk_id)
    ulasan = Ulasan.query.filter_by(produk_id=produk_id).all()
    rata_bintang = round(sum(u.bintang for u in ulasan) / len(ulasan), 1) if ulasan else 0
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Login dulu untuk memberikan ulasan!')
            return redirect(url_for('login'))
        ulasan_baru = Ulasan(
            user_id=current_user.id,
            produk_id=produk_id,
            bintang=int(request.form['bintang']),
            komentar=request.form['komentar']
        )
        db.session.add(ulasan_baru)
        notif_penjual = Notifikasi(
            user_id=produk.user_id,
            pesan=f'{current_user.nama} memberikan ulasan ⭐{request.form["bintang"]} untuk produk "{produk.nama}": "{request.form["komentar"][:50]}..."',
            link=f'/produk/{produk_id}'
        )
        db.session.add(notif_penjual)
        db.session.commit()
        flash('Ulasan berhasil ditambahkan!')
        return redirect(url_for('detail_produk', produk_id=produk_id))
    return render_template('detail.html', produk=produk, ulasan=ulasan, rata_bintang=rata_bintang)

@app.route('/keranjang/tambah/<int:produk_id>')
@login_required
def tambah_keranjang(produk_id):
    produk = Produk.query.get_or_404(produk_id)
    if produk.stok <= 0:
        flash(f'Maaf, stok "{produk.nama}" sudah habis!')
        return redirect(url_for('detail_produk', produk_id=produk_id))
    item = Keranjang(user_id=current_user.id, produk_id=produk_id)
    db.session.add(item)
    db.session.commit()
    flash('Produk ditambahkan ke keranjang!')
    return redirect(url_for('keranjang'))

@app.route('/keranjang')
@login_required
def keranjang():
    items = Keranjang.query.filter_by(user_id=current_user.id).all()
    return render_template('keranjang.html', items=items)

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = Keranjang.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Keranjang masih kosong!')
        return redirect(url_for('keranjang'))
    alamat_list = Alamat.query.filter_by(user_id=current_user.id).all()
    if not alamat_list:
        flash('Tambah alamat pengiriman dulu!')
        return redirect(url_for('tambah_alamat'))
    if request.method == 'POST':
        alamat_id = int(request.form['alamat_id'])
        alamat = Alamat.query.get(alamat_id)
        ongkir = hitung_ongkir(alamat.kota)
        alamat_str = f"{alamat.nama_penerima}, {alamat.no_hp}, {alamat.alamat_lengkap}, {alamat.kota}, {alamat.provinsi} {alamat.kode_pos}"
        for item in items:
            produk = Produk.query.get(item.produk_id)
            if produk.stok < item.jumlah:
                flash(f'Stok "{produk.nama}" tidak mencukupi! Sisa: {produk.stok}')
                return redirect(url_for('keranjang'))
            produk.stok -= item.jumlah
            order_baru = Order(
                user_id=current_user.id,
                produk_id=item.produk_id,
                jumlah=item.jumlah,
                total_harga=(produk.harga * item.jumlah) + ongkir,
                ongkir=ongkir,
                alamat_pengiriman=alamat_str
            )
            db.session.add(order_baru)
            notif_penjual = Notifikasi(
                user_id=produk.user_id,
                pesan=f'Pesanan baru untuk "{produk.nama}" dari {current_user.nama}! Dikirim ke: {alamat.kota}',
                link='/pesanan-masuk'
            )
            db.session.add(notif_penjual)
            db.session.delete(item)
        db.session.commit()
        flash('Pesanan berhasil dibuat!')
        return redirect(url_for('riwayat'))
    alamat_utama = Alamat.query.filter_by(user_id=current_user.id, is_utama=True).first() or alamat_list[0]
    ongkir_preview = hitung_ongkir(alamat_utama.kota)
    total_belanja = sum(Produk.query.get(i.produk_id).harga * i.jumlah for i in items)
    return render_template('checkout.html',
        items=items,
        alamat_list=alamat_list,
        alamat_utama=alamat_utama,
        ongkir_preview=ongkir_preview,
        total_belanja=total_belanja
    )

@app.route('/riwayat')
@login_required
def riwayat():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.tanggal.desc()).all()
    return render_template('riwayat.html', orders=orders)

@app.route('/order/bukti/<int:order_id>', methods=['POST'])
@login_required
def upload_bukti(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Kamu tidak berhak mengupload bukti ini!')
        return redirect(url_for('riwayat'))
    if 'bukti' not in request.files:
        flash('Pilih file bukti pembayaran!')
        return redirect(url_for('riwayat'))
    foto = request.files['bukti']
    if foto.filename == '':
        flash('Pilih file bukti pembayaran!')
        return redirect(url_for('riwayat'))
    filename = secure_filename(f'bukti_{order_id}_{foto.filename}')
    foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    order.bukti_bayar = filename
    order.status = 'Menunggu Konfirmasi'
    produk = Produk.query.get(order.produk_id)
    notif = Notifikasi(
        user_id=produk.user_id,
        pesan=f'{current_user.nama} telah upload bukti pembayaran untuk produk "{produk.nama}"!',
        link='/pesanan-masuk'
    )
    db.session.add(notif)
    db.session.commit()
    flash('Bukti pembayaran berhasil diupload!')
    return redirect(url_for('riwayat'))

@app.route('/order/konfirmasi/<int:order_id>')
@login_required
def konfirmasi_bayar(order_id):
    order = Order.query.get_or_404(order_id)
    produk = Produk.query.get(order.produk_id)
    if produk.user_id != current_user.id:
        flash('Kamu tidak berhak mengkonfirmasi pesanan ini!')
        return redirect(url_for('pesanan_masuk'))
    order.status = 'Diproses'
    notif = Notifikasi(
        user_id=order.user_id,
        pesan=f'Pembayaran kamu untuk produk "{produk.nama}" telah dikonfirmasi! Pesanan sedang diproses.',
        link='/riwayat'
    )
    db.session.add(notif)
    db.session.commit()
    flash('Pembayaran berhasil dikonfirmasi!')
    return redirect(url_for('pesanan_masuk'))

@app.route('/order/status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    produk = Produk.query.get(order.produk_id)
    if produk.user_id != current_user.id:
        flash('Kamu tidak berhak mengubah status ini!')
        return redirect(url_for('profil'))
    status_baru = request.form['status']
    order.status = status_baru
    notif_pembeli = Notifikasi(
        user_id=order.user_id,
        pesan=f'Status pesanan "{produk.nama}" diubah menjadi: {status_baru}',
        link='/riwayat'
    )
    db.session.add(notif_pembeli)
    db.session.commit()
    flash('Status pesanan berhasil diupdate!')
    return redirect(url_for('pesanan_masuk'))

@app.route('/pesanan-masuk')
@login_required
def pesanan_masuk():
    produk_saya = Produk.query.filter_by(user_id=current_user.id).all()
    produk_ids = [p.id for p in produk_saya]
    orders = Order.query.filter(Order.produk_id.in_(produk_ids)).order_by(Order.tanggal.desc()).all()
    return render_template('pesanan_masuk.html', orders=orders)

@app.route('/notifikasi')
@login_required
def notifikasi():
    notifs = Notifikasi.query.filter_by(user_id=current_user.id).order_by(Notifikasi.tanggal.desc()).all()
    for n in notifs:
        n.dibaca = True
    db.session.commit()
    return render_template('notifikasi.html', notifs=notifs)

@app.route('/alamat')
@login_required
def alamat():
    alamat_list = Alamat.query.filter_by(user_id=current_user.id).all()
    return render_template('alamat.html', alamat_list=alamat_list)

@app.route('/alamat/tambah', methods=['GET', 'POST'])
@login_required
def tambah_alamat():
    if request.method == 'POST':
        is_utama = request.form.get('is_utama') == 'on'
        if is_utama:
            Alamat.query.filter_by(user_id=current_user.id).update({'is_utama': False})
        alamat_baru = Alamat(
            user_id=current_user.id,
            nama_penerima=request.form['nama_penerima'],
            no_hp=request.form['no_hp'],
            alamat_lengkap=request.form['alamat_lengkap'],
            kota=request.form['kota'],
            provinsi=request.form['provinsi'],
            kode_pos=request.form['kode_pos'],
            is_utama=is_utama
        )
        db.session.add(alamat_baru)
        db.session.commit()
        flash('Alamat berhasil ditambahkan!')
        return redirect(url_for('alamat'))
    return render_template('tambah_alamat.html')

@app.route('/alamat/hapus/<int:alamat_id>')
@login_required
def hapus_alamat(alamat_id):
    a = Alamat.query.get_or_404(alamat_id)
    if a.user_id != current_user.id:
        flash('Kamu tidak berhak menghapus alamat ini!')
        return redirect(url_for('alamat'))
    db.session.delete(a)
    db.session.commit()
    flash('Alamat berhasil dihapus!')
    return redirect(url_for('alamat'))

@app.route('/profil')
@login_required
def profil():
    produk_saya = Produk.query.filter_by(user_id=current_user.id).all()
    orders_saya = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('profil.html', produk_saya=produk_saya, orders_saya=orders_saya)

@app.route('/profil/edit', methods=['GET', 'POST'])
@login_required
def edit_profil():
    if request.method == 'POST':
        current_user.nama = request.form['nama']
        if request.files['foto'].filename != '':
            foto = request.files['foto']
            filename = secure_filename(f'profil_{current_user.id}_{foto.filename}')
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.foto_profil = filename
        db.session.commit()
        flash('Profil berhasil diupdate!')
        return redirect(url_for('profil'))
    return render_template('edit_profil.html')

@app.route('/profil/ganti-password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if request.method == 'POST':
        password_lama = request.form['password_lama']
        password_baru = request.form['password_baru']
        konfirmasi = request.form['konfirmasi']
        if not check_password_hash(current_user.password, password_lama):
            flash('Password lama salah!')
            return redirect(url_for('ganti_password'))
        if password_baru != konfirmasi:
            flash('Konfirmasi password tidak cocok!')
            return redirect(url_for('ganti_password'))
        current_user.password = generate_password_hash(password_baru)
        db.session.commit()
        flash('Password berhasil diganti!')
        return redirect(url_for('profil'))
    return render_template('ganti_password.html')

@app.route('/produk/edit/<int:produk_id>', methods=['GET', 'POST'])
@login_required
def edit_produk(produk_id):
    produk = Produk.query.get_or_404(produk_id)
    if produk.user_id != current_user.id:
        flash('Kamu tidak berhak mengedit produk ini!')
        return redirect(url_for('profil'))
    if request.method == 'POST':
        produk.nama = request.form['nama']
        produk.harga = int(request.form['harga'])
        produk.stok = int(request.form['stok'])
        produk.deskripsi = request.form['deskripsi']
        produk.kategori = request.form['kategori']
        if request.files['foto'].filename != '':
            foto = request.files['foto']
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            produk.foto = filename
        db.session.commit()
        flash('Produk berhasil diupdate!')
        return redirect(url_for('profil'))
    return render_template('edit_produk.html', produk=produk, kategori_list=KATEGORI_LIST)

@app.route('/produk/hapus/<int:produk_id>')
@login_required
def hapus_produk(produk_id):
    produk = Produk.query.get_or_404(produk_id)
    if produk.user_id != current_user.id:
        flash('Kamu tidak berhak menghapus produk ini!')
        return redirect(url_for('profil'))
    db.session.delete(produk)
    db.session.commit()
    flash('Produk berhasil dihapus!')
    return redirect(url_for('profil'))

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_user = User.query.count()
    total_produk = Produk.query.count()
    total_order = Order.query.count()
    total_pendapatan = db.session.query(db.func.sum(Order.total_harga)).scalar() or 0
    orders_terbaru = Order.query.order_by(Order.tanggal.desc()).limit(5).all()
    produk_terbaru = Produk.query.order_by(Produk.tanggal.desc()).limit(5).all()
    users = User.query.all()
    return render_template('admin/dashboard.html',
        total_user=total_user, total_produk=total_produk,
        total_order=total_order, total_pendapatan=total_pendapatan,
        orders_terbaru=orders_terbaru, produk_terbaru=produk_terbaru, users=users)

@app.route('/admin/produk')
@login_required
@admin_required
def admin_produk():
    produk = Produk.query.order_by(Produk.tanggal.desc()).all()
    return render_template('admin/produk.html', produk=produk)

@app.route('/admin/produk/hapus/<int:produk_id>')
@login_required
@admin_required
def admin_hapus_produk(produk_id):
    produk = Produk.query.get_or_404(produk_id)
    Ulasan.query.filter_by(produk_id=produk_id).delete()
    Keranjang.query.filter_by(produk_id=produk_id).delete()
    Order.query.filter_by(produk_id=produk_id).delete()
    db.session.delete(produk)
    db.session.commit()
    flash('Produk berhasil dihapus!')
    return redirect(url_for('admin_produk'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/hapus/<int:user_id>')
@login_required
@admin_required
def admin_hapus_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Tidak bisa hapus akun admin!')
        return redirect(url_for('admin_users'))
    Notifikasi.query.filter_by(user_id=user_id).delete()
    Ulasan.query.filter_by(user_id=user_id).delete()
    Keranjang.query.filter_by(user_id=user_id).delete()
    Order.query.filter_by(user_id=user_id).delete()
    produk_user = Produk.query.filter_by(user_id=user_id).all()
    for p in produk_user:
        Ulasan.query.filter_by(produk_id=p.id).delete()
        Keranjang.query.filter_by(produk_id=p.id).delete()
        Order.query.filter_by(produk_id=p.id).delete()
        db.session.delete(p)
    db.session.delete(user)
    db.session.commit()
    flash('User berhasil dihapus!')
    return redirect(url_for('admin_users'))

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.tanggal.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/setup')
def admin_setup():
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        flash('Admin sudah ada!')
        return redirect(url_for('index'))
    admin_baru = User(
        nama='Admin',
        email='admin@marketplace.com',
        password=generate_password_hash('admin123'),
        is_admin=True
    )
    db.session.add(admin_baru)
    db.session.commit()
    flash('Akun admin berhasil dibuat!')
    return redirect(url_for('login'))
# ===== TOKO PROFIL PENJUAL =====
@app.route('/toko/<int:user_id>')
def toko(user_id):
    penjual = User.query.get_or_404(user_id)
    produk_toko = Produk.query.filter_by(user_id=user_id).all()
    total_produk = len(produk_toko)
    total_terjual = db.session.query(db.func.sum(Order.jumlah)).filter(
        Order.produk_id.in_([p.id for p in produk_toko])
    ).scalar() or 0
    ulasan_toko = Ulasan.query.filter(
        Ulasan.produk_id.in_([p.id for p in produk_toko])
    ).all()
    rata_toko = round(sum(u.bintang for u in ulasan_toko) / len(ulasan_toko), 1) if ulasan_toko else 0
    return render_template('toko.html',
        penjual=penjual,
        produk_toko=produk_toko,
        total_produk=total_produk,
        total_terjual=total_terjual,
        rata_toko=rata_toko,
        total_ulasan=len(ulasan_toko)
    )
@app.route('/login/google/callback')
def google_login_callback():
    if not google.authorized:
        flash('Login Google gagal!')
        return redirect(url_for('login'))
    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Gagal mengambil data dari Google!')
        return redirect(url_for('login'))
    info = resp.json()
    email = info['email']
    nama = info['name']
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            nama=nama,
            email=email,
            password=generate_password_hash(os.urandom(16).hex())
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Akun baru dibuat untuk {nama}!')
    login_user(user)
    flash(f'Selamat datang, {nama}!')
    return redirect(url_for('index'))
# ===== HAPUS RIWAYAT ORDER =====
@app.route('/order/hapus/<int:order_id>')
@login_required
def hapus_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Kamu tidak berhak menghapus pesanan ini!')
        return redirect(url_for('riwayat'))
    if order.status not in ['Selesai', 'Dibatalkan']:
        flash('Hanya pesanan yang sudah Selesai atau Dibatalkan yang bisa dihapus!')
        return redirect(url_for('riwayat'))
    db.session.delete(order)
    db.session.commit()
    flash('Riwayat pesanan berhasil dihapus!')
    return redirect(url_for('riwayat'))

if __name__ == '__main__':
    with app.app_context():
        os.makedirs('static/uploads', exist_ok=True)
        db.create_all()
    app.run(debug=True)