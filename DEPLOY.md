# دليل التشغيل والنشر - تمكّن

## 1. التشغيل المحلي (Local Development)

### المتطلبات
- Python 3.10+
- pip

### الخطوات

```bash
# 1. انتقل لمجلد المشروع
cd tamakun-saas

# 2. أنشئ بيئة افتراضية (اختياري لكن مستحسن)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. ثبّت المتطلبات
pip install -r requirements.txt

# 4. انسخ ملف البيئة
copy .env.example .env
# عدّل القيم في .env حسب الحاجة

# 5. شغّل التطبيق
python run.py
```

التطبيق سيعمل على: http://localhost:8000

### بيانات الدخول الافتراضية للمدير
- البريد: m.alshathri@tamakun.sa
- كلمة المرور: Tamakun@2024

---

## 2. النشر على cPanel (Setup Python App + Passenger)

### الخطوة 1: رفع المشروع
1. اضغط الملفات في ملف مضغوط (zip)
2. ارفعها عبر File Manager في cPanel
3. فك الضغط في المسار المطلوب (مثلاً: `/home/username/tamakun-saas/`)

### الخطوة 2: إنشاء قاعدة البيانات MySQL
1. من cPanel افتح **MySQL Databases**
2. أنشئ قاعدة بيانات جديدة (مثال: `username_tamakun`)
3. أنشئ مستخدم جديد وأعطه كل الصلاحيات على القاعدة

### الخطوة 3: إعداد تطبيق Python
1. من cPanel افتح **Setup Python App**
2. اضغط **Create Application**
3. املأ الحقول:
   - Python version: `3.10` أو أعلى
   - Application root: `tamakun-saas`
   - Application URL: اختر الدومين/المسار
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
4. اضغط **Create**

### الخطوة 4: تثبيت المتطلبات
1. من صفحة التطبيق في cPanel، انسخ أمر تفعيل البيئة الافتراضية:
   ```
   source /home/username/virtualenv/tamakun-saas/3.10/bin/activate
   ```
2. افتح **Terminal** في cPanel
3. فعّل البيئة الافتراضية (الصق الأمر أعلاه)
4. ثبّت المتطلبات:
   ```bash
   cd ~/tamakun-saas
   pip install -r requirements-cpanel.txt
   ```

### الخطوة 5: إعداد متغيرات البيئة
من صفحة تطبيق Python في cPanel، أضف المتغيرات التالية:

| المتغير | القيمة |
|---------|--------|
| `SECRET_KEY` | مفتاح سري طويل وعشوائي |
| `DATABASE_URL` | `mysql+pymysql://user:pass@localhost/dbname` |
| `EXTERNAL_DB_HOST` | `37.27.130.230` |
| `EXTERNAL_DB_PORT` | `5432` |
| `EXTERNAL_DB_USERNAME` | `ingest_user` |
| `EXTERNAL_DB_PASSWORD` | `27nQ8Bi1ur` |
| `EXTERNAL_DB_NAME` | `ingest_tamakun` |

أو أنشئ ملف `.env` في مجلد المشروع.

### الخطوة 6: إعادة تشغيل التطبيق
1. من صفحة Setup Python App اضغط **Restart**
2. أو من Terminal:
   ```bash
   touch ~/tamakun-saas/tmp/restart.txt
   ```

### الخطوة 7: التحقق
- افتح الرابط في المتصفح
- سجّل دخول كمدير
- ارفع ملف تجريبي

---

## 3. استكشاف الأخطاء

### التطبيق لا يعمل
- تأكد من تثبيت `a2wsgi` (مطلوب لتحويل ASGI -> WSGI)
- تحقق من ملف الأخطاء: `~/tamakun-saas/stderr.log`
- تحقق من صلاحيات مجلدي `uploads/` و `exports/`:
  ```bash
  chmod 755 uploads/ exports/
  ```

### خطأ في قاعدة البيانات
- تأكد من صحة `DATABASE_URL`
- تأكد من تثبيت `pymysql`
- تأكد من صلاحيات المستخدم على القاعدة

### الملفات الثابتة لا تظهر
- تأكد من وجود مجلد `app/static/` بملفاته
- في بعض إعدادات cPanel قد تحتاج إعداد alias في `.htaccess`

---

## 4. هيكل المشروع

```
tamakun-saas/
├── app/
│   ├── __init__.py
│   ├── config.py              # الإعدادات
│   ├── database.py            # اتصال قاعدة البيانات
│   ├── main.py                # تطبيق FastAPI + المسارات
│   ├── models.py              # نماذج SQLAlchemy
│   ├── brands/
│   │   ├── __init__.py        # مصنع المعالجات
│   │   ├── base.py            # الصنف الأساسي
│   │   ├── bestshield.py      # معالج بست شيلد
│   │   ├── shabah.py          # معالج شبة
│   │   └── alarabi.py         # معالج أقمشة العربي
│   ├── services/
│   │   ├── __init__.py
│   │   └── auth.py            # المصادقة والجلسات
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/dashboard.js
│   └── templates/
│       ├── base.html
│       ├── home.html
│       ├── dashboard.html
│       ├── admin_login.html
│       ├── admin_home.html
│       ├── admin_password.html
│       ├── admin_stores.html
│       └── admin_sku_rules.html
├── uploads/                   # ملفات المستخدمين المرفوعة
├── exports/                   # ملفات Excel المصدّرة
├── .env.example
├── .gitignore
├── requirements.txt           # متطلبات التشغيل المحلي
├── requirements-cpanel.txt    # متطلبات cPanel
├── run.py                     # نقطة تشغيل محلي
└── passenger_wsgi.py          # نقطة دخول cPanel/Passenger
```
