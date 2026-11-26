T-BOOSTER v1.1.2
Yapımcı: TarikPro43391

Windows için sade ve hızlı bir performans / sistem bakım aracı. Kapalı kaynaklı bir
.exe değil, sıradan bir Python programıdır; tüm kod açık ve okunabilir.

BAŞLATMA
  1) (İsteğe bağlı) T_BOOSTER_KISAYOL_OLUSTUR.bat  -> masaüstüne kısayol oluşturur
  2) t-booster.bat dosyasını aç
  veya:  python T_BOOSTER_V1_1_2.py

GEREKSİNİMLER
  - Windows 10 / 11, Tkinter ile Python 3.10 veya üzeri
  - (Önerilir) Pillow:  pip install pillow
  - Program yönetici yetkisiyle açılır (sistem ayarlarını değiştirebilmesi için).

ARAÇ KUTUSU — 26 araç, 5 kategori (sekmelerden seçilir)

  Bakım
    - Sistem Sağlık Puanı          RAM, disk, açık kalma süresi vb. ile 0-100 puan
    - Geçici Dosya Temizleyici     Temp, çökme dökümleri, hata raporları (1 günden eski)
    - Gizlilik Temizleyici         Pano, son dosyalar, atlama listeleri, Win+R / adres çubuğu / arama geçmişi
    - Geri Yükleme Noktası         Tek tıkla Windows geri yükleme noktası
    - Hızlı Sorun Giderici         Yazıcı kuyruğu, simge önbelleği, ağ yığını, Windows Update önbelleği

  Disk & Dosya
    - Büyük Dosya Bulucu           Yalnızca listeler
    - Yinelenen Dosya Bulucu       Aynı içerikli dosyalar; yalnızca listeler
    - Klasör Boyutu Analizi        Hangi klasör ne kadar yer kaplıyor; içine inilebilir
    - Disk Optimizasyonu           SSD için TRIM, HDD için birleştirme
    - Dosya Karma (Hash)           MD5 / SHA-1 / SHA-256 hesaplar, yapıştırılan karmayla karşılaştırır

  Performans
    - Arka Plan Uygulama Avcısı    RAM'i en çok kullanan uygulamalar
    - Başlangıç Uygulamaları       Yedekli açma/kapama asistanını açar
    - Güç Planı Yöneticisi         Dengeli / Yüksek performans / Güç tasarrufu
    - Pil Sağlığı Raporu           Dizüstü bilgisayarlar için
    - Yüklü Programlar             Boyuta göre liste, arama, kaldırıcıyı açar

  Ağ
    - DNS & Ağ Hızlandırıcı        DNS önbelleğini temizler, DNS sunucularını ölçer
    - İnternet Hız Testi           İndirme, yükleme, gecikme
    - Açık Ağ Bağlantıları         Hangi uygulama nereye bağlı (netstat), tüm ağa açık portlar vurgulanır
    - Ağdaki Cihazlar              Yerel ağdaki cihazlar (yalnızca özel ağlarda çalışır)
    - Ping ve Yol İzleme           Gecikme, kayıp, sapma; atlama atlama yol

  Güvenlik & Sistem
    - Kayıtlı Wi-Fi Şifreleri      Varsayılan gizli, GÖSTER'e basman gerekir
    - Sistem Dosyası Denetleyici   SFC; "sadece denetle" veya "denetle ve onar"
    - Hosts Dosyası Denetimi       Şüpheli yönlendirmeleri işaretler; yalnızca okur
    - Son Hatalar (Olay Günlüğü)   Çökme, mavi ekran, donanım hataları; Türkçe açıklamalarla
    - Zamanlanmış Görevler         Microsoft dışı görevler; şüpheli olanları işaretler
    - Windows Güncelleme Geçmişi   Yüklü güncellemeler (KB)

BOOST VE KURTARMA
  Gerçek FPS Modu, Akıllı Boost, Ultra Boost Max (200+ tweak), Oyun Modu, Roblox FPS Kilidi,
  Windows Ayarları, Sürücü Merkezi, Disk Info (SMART), FPS Lab ve güvenli geri alma.

BİLİNMESİ GEREKENLER
  - Değişiklik yapmadan önce bir geri yükleme noktası oluştur
    (Araç Kutusu > Bakım). Özellikle SFC onarımından, ağ yığını ve Windows Update
    sıfırlamalarından önce.
  - Listeleme araçları (büyük/yinelenen dosya, klasör analizi, bağlantılar, hosts, olay
    günlüğü, görevler, güncellemeler) yalnızca okur; değişiklik yapan her işlem onay ister.
  - "Ağdaki Cihazlar" yalnızca bağlı olduğun özel (yerel) ağı tarar; sadece kendi ağında kullan.
  - Bazı bilgisayarlarda Windows/Defender yanlışlıkla uyarı verebilir (yanlış pozitif).
    Kaynağı herhangi bir metin düzenleyicide inceleyebilirsin.
  - Discord bağlantısı yok, veri toplama yok; tamamen yerel çalışır.


v1.1.0 yenilikleri
- Yüksek DPI için yuvarlak açma-kapama anahtarları
- Sayfa arama (Ctrl+K)
- Tweak seçim profillerini kaydetme ve yükleme
- Sistem özetini panoya kopyalama
- Pencereyi en üstte tutma
- İşlem günlüğünü metin dosyasına aktarma

v1.1.2 yenilikleri
- Kontrol Merkezi’nde Intel Maksimum Performans kartına Intel logosu eklendi. Intel, AMD ve NVIDIA logolarının yüksek DPI boyutları güncellendi.
- Sol menüde her bölüm için farklı, pürüzsüz bir ikon kullanılıyor.
- Kontrol Merkezi kartlarının ve sayfa arama düğmesinin köşeleri yuvarlatıldı. Dar alanda kart başlıkları alt satıra geçiyor.
- Düğmelerde ve açık durumdaki anahtarlarda T-BOOSTER logosundan alınan koyu mavi kullanılıyor.
- Sol menüde VPN > Erişim Engeli Açma, turkey_dnsredir.cmd profilini açar. Aynı düğmeyle veya T-BOOSTER'ı kapatarak durdurabilirsin.
