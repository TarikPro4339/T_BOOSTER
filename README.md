# T-Booster

**Sürüm:** v1.0.5 &nbsp;•&nbsp; **Yapımcı:** TarikPro43391

T-Booster, Windows için sade ve hızlı bir performans/sistem bakım aracıdır. Tek bir pencereden; sistemini hızlandırmanı, donanımını incelemeni, gereksiz dosyaları temizlemeni ve geri alınabilir ayarlarla oynamanı sağlar. Kapalı kaynaklı bir `.exe` değil, sıradan bir Python programıdır — tüm kodu açık ve okunabilir.

---

## ▶️ Başlatma

1. **(İsteğe bağlı)** `T_BOOSTER_KISAYOL_OLUSTUR.bat` dosyasını çalıştır — masaüstüne T-Booster logolu bir kısayol oluşturur.
2. `t-booster.bat` dosyasını aç.

Python 3 kurulu değilse program seni bilgilendirir. Elle çalıştırmak istersen:
```
python T_BOOSTER_V1_0_5.py
```

### Gereksinimler
- Windows 10 / 11
- Python 3
- *(Önerilir)* Pillow — pürüzsüz arayüz için: `pip install pillow`

---

## 🧰 Araç Kutusu — 11 özellik

| # | Özellik | Ne yapar |
|---|---|---|
| 1 | **Sistem Sağlık Puanı** | RAM, disk, açık kalma süresi, başlangıç uygulamaları ve geçici dosyalara göre 0-100 arası puan verir |
| 2 | **Geçici Dosya Temizleyici** | Temp, Windows Temp, çökme dökümleri ve hata raporlarını temizler (yalnızca 1 günden eski dosyalar) |
| 3 | **DNS & Ağ Hızlandırıcı** | DNS önbelleğini temizler, popüler DNS sunucularının gecikmesini ölçüp en hızlısını işaretler |
| 4 | **Büyük Dosya Bulucu** | Seçtiğin klasördeki en büyük dosyaları listeler — hiçbir şeyi silmez |
| 5 | **Arka Plan Uygulama Avcısı** | RAM'i en çok kullanan uygulamaları listeler, seçileni kapatır (sistem işlemleri korumalıdır) |
| 6 | **Başlangıç Uygulamaları** | Run kayıtlarını ve Başlangıç klasörünü listeler, yayıncı/etki tahmini sunar; kapattığın her girdi yedeklenir |
| 7 | **Kayıtlı Wi-Fi Şifreleri** | Bu bilgisayara kayıtlı ağların şifrelerini gösterir (varsayılan gizli, GÖSTER'e basman gerekir) |
| 8 | **Geri Yükleme Noktası Oluştur** | Tek tıkla Windows Sistem Geri Yükleme noktası oluşturur |
| 9 | **Güç Planı Yöneticisi** | Dengeli / Yüksek Performans / Güç Tasarrufu planları arasında geçiş yapar |
| 10 | **İnternet Hız Testi** | İndirme, yükleme ve gecikmeyi ölçer |
| 11 | **Pil Sağlığı Raporu** | Dizüstü bilgisayarlarda tasarım kapasitesi, güncel kapasite ve döngü sayısını gösterir |

---

## 🚀 Boost ve Kurtarma
- **Gerçek FPS Modu** — GPU tercihi, güç planı, Game Mode, DVR ve daha fazlasını tek seferde ayarlar
- **Akıllı Boost** — temel FPS, oyun ve güvenli Windows ayarlarını uygular
- **Ultra Boost Max** — 200'den fazla tweak'i gelişmiş CPU/NVMe/oyun ayarlarıyla birlikte uygular
- **Güvenli geri alma** — yapılan her değişiklik kayıt altında, istediğin zaman eski haline döndürebilirsin

## 🖥️ Sistem Bilgisi
Kontrol Merkezi'nde canlı CPU/GPU/RAM/disk kartlarının yanında: **BIOS sürümü**, **anakart modeli**, **işlemci modeli**, **RAM kapasitesi** ve **işletim sistemi sürümü**. Ayrıca T-Booster Disk Info sayfasında SMART/sağlık verileri, Performans Araçları'nda sürücü ve FPS analizi bulunur.

## 🎮 Oyun ve Donanım
- **Oyun Modu** — tek tıkla oyun odaklı sistem ayarları
- **Roblox FPS Kilidi** — FPS sınırlamasını kaldırır
- **Windows Ayarları** — ince Windows ayarları
- **200 Tweak Paketi** — performans, ağ, gizlilik ve arayüz kategorilerinde kapsamlı ayar seti

---

## 🎨 Arayüz
- Sade, düz (flat) modern tasarım — koyu temada mat siyah (`#1E1E1E` / `#252526`), açık temada gözü yormayan kırık beyaz (`#FAFAFA` / `#F5F5F5`)
- Koyu / açık tema seçimi, tüm açma-kapama düğmeleri her zaman mavi
- Akıcı açılış ve sayfa geçiş animasyonları
- Pürüzsüz (antialiased) düğmeler, yuvarlak kartlar, keskin vektör menü ikonları

---

## ⚠️ Bilinmesi gerekenler
- Bazı bilgisayarlarda Windows/Defender bu programı yanlışlıkla virüs olarak işaretleyebilir (yanlış pozitif). Program kapalı kaynaklı bir `.exe` değil, sıradan bir Python betiğidir — kaynağını herhangi bir metin düzenleyicide inceleyebilirsin. Uyarı çıkarsa "Daha fazla bilgi" → "Yine de çalıştır" seçeneğini kullanabilir veya klasörü Defender hariç tutma listesine ekleyebilirsin.
- Değişiklik yapmadan önce bir Windows geri yükleme noktası oluşturman önerilir (Araç Kutusu'nda tek tıkla yapabilirsin).
- Pil sağlığı raporu yalnızca dizüstü bilgisayarlarda çalışır.
- Discord bağlantısı yok, veri toplama yok — tamamen yerel çalışır.

---

## 📁 Proje dosyaları
| Dosya | Açıklama |
|---|---|
| `t-booster.bat` | Programı başlatır |
| `T_BOOSTER_KISAYOL_OLUSTUR.bat` | Masaüstü kısayolu oluşturur |
| `T_BOOSTER_V1_0_5.py` | Ana uygulama |
| `tb_core.py` | Çekirdek sistem/donanım modülü |
| `tb_tools.py`, `tb_suite.py`, `tb_features.py` | Araç ve özellik modülleri |
| `TB.ico`, `TB_logo.png` | Uygulama ikonu ve logosu |
