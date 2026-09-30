# T-BOOSTER — Yeni Gelen Özellikler
**Sürüm:** v1.0.0 &nbsp;•&nbsp; **Yapımcı:** TarikPro43391

---

## 🧰 Araç Kutusu (5 yeni özellik)

Kenar çubuğundaki **Araç Kutusu** sayfasına eklendi.

### 1. Sistem Sağlık Puanı
RAM kullanımı, disk boş alanı, açık kalma süresi, başlangıç uygulaması sayısı ve geçici dosya miktarına göre **0-100 arası puan** hesaplar. Puanı bir halka grafikte gösterir, altında da neyi düzeltmen gerektiğini yazar (örn. "Sistem diski boş alanı düşük — geçici dosyaları temizle").

### 2. Geçici Dosya Temizleyici
Kullanıcı Temp, Windows Temp, çökme dökümleri ve Windows hata raporlarını temizler.
- Yalnızca **1 günden eski** dosyalar silinir
- Kullanımdaki dosyalar otomatik atlanır
- Önce **TARA** ile ne kadar yer açılacağını gösterir, sonra onay ister
- İstersen geri dönüşüm kutusunu da boşaltabilir (varsayılan kapalı)

### 3. DNS ve Ağ Hızlandırıcı
- Windows DNS önbelleğini tek tıkla temizler
- Cloudflare, Google, Quad9, OpenDNS ve AdGuard sunucularının gecikmesini ölçüp **en hızlısını işaretler**
- DNS'i otomatik değiştirmez, Windows ağ ayarlarını açar

### 4. Büyük Dosya Bulucu
Seçtiğin klasördeki en büyük dosyaları listeler ve dosya gezgininde konumunu açar. **Hiçbir şeyi silmez**, sadece gösterir.

### 5. Arka Plan Uygulama Avcısı
RAM'i en çok kullanan uygulamaları listeler; tarayıcı, sohbet uygulaması gibi oyun öncesi kapatılabilecekleri işaretler. Seçileni onay alarak kapatır. **Sistem işlemleri korumalıdır**, yanlışlıkla kapatılamaz.

---

## 🖥️ Sistem Bilgisi Kartları

Kontrol Merkezi sayfasına, üst metrik kartlarının altına 5 yeni bilgi kartı eklendi:

| Kart | İçerik |
|---|---|
| 🧾 BIOS Sürümü | Üretici + sürüm numarası |
| 🧩 Anakart Modeli | Üretici + model |
| 🧠 İşlemci Modeli | Tam CPU adı |
| 💾 RAM Kapasitesi | Toplam kapasite + modül sayısı |
| 🪟 İşletim Sistemi | Windows sürümü + build numarası |

---

## 🎨 Görsel Yenilikler
- **Yeni logo** ve çok boyutlu uygulama ikonu (16-256 px)
- **Sade, düz (flat) arayüz:** koyu temada VS Code tarzı mat siyah, açık temada gözü yormayan kırık beyaz
- Açma/kapama düğmeleri artık **hepsi mavi** (açık durumda)
- Menü ikonları yeniden çizildi, keskin ve net
- Marka logoları (Acer, ASUS, Dell, HP, Intel, Lenovo, MSI, NVIDIA, AMD) ve Roblox/Minecraft ikonları güncellendi
- Masaüstü kısayolu oluşturucu (`T_BOOSTER_KISAYOL_OLUSTUR.bat`)

---

## 🛠️ Arka Plan Düzeltmeleri
- **Virüs uyarısı:** Programın çekirdek kodu artık şifrelenip gizlenmiyor; sıradan, okunabilir bir dosya olarak geliyor. Bu, Windows Defender'ın "dropper" şüphesiyle yanlış pozitif vermesinin en büyük sebebiydi.
- **"Okunamadı" hatası:** BIOS/Anakart/İşlemci/RAM/Disk bilgilerini okuyan koddaki bir hata düzeltildi; artık bu bilgiler doğru şekilde geliyor.
- Discord bağlantıları tamamen kaldırıldı
- Tüm "EFG" ve "Beta" ifadeleri temizlendi, sürüm **v1.0.0 (final)** oldu
