from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    foto_profil = db.Column(db.String(200), nullable=True)
    no_hp = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    produk = db.relationship('Produk', backref='penjual', lazy=True)
    
class Produk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(200), nullable=False)
    harga = db.Column(db.Integer, nullable=False)
    stok = db.Column(db.Integer, nullable=False)
    deskripsi = db.Column(db.Text, nullable=False)
    foto = db.Column(db.String(200), nullable=False)
    kategori = db.Column(db.String(100), default='Lainnya')
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ulasan = db.relationship('Ulasan', backref='produk', lazy=True)

class Keranjang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    produk_id = db.Column(db.Integer, db.ForeignKey('produk.id'), nullable=False)
    jumlah = db.Column(db.Integer, default=1)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    produk_id = db.Column(db.Integer, db.ForeignKey('produk.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    total_harga = db.Column(db.Integer, nullable=False)
    ongkir = db.Column(db.Integer, default=0)
    alamat_pengiriman = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='Menunggu Pembayaran')
    bukti_bayar = db.Column(db.String(200), nullable=True)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    produk = db.relationship('Produk', backref='orders')

class Ulasan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    produk_id = db.Column(db.Integer, db.ForeignKey('produk.id'), nullable=False)
    bintang = db.Column(db.Integer, nullable=False)
    komentar = db.Column(db.Text, nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='ulasan')

class Alamat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nama_penerima = db.Column(db.String(100), nullable=False)
    no_hp = db.Column(db.String(20), nullable=False)
    alamat_lengkap = db.Column(db.Text, nullable=False)
    kota = db.Column(db.String(100), nullable=False)
    provinsi = db.Column(db.String(100), nullable=False)
    kode_pos = db.Column(db.String(10), nullable=False)
    is_utama = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='alamat')

class Notifikasi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pesan = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), default='/')
    dibaca = db.Column(db.Boolean, default=False)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notifikasi')