# T-BOOSTER

**v1.1.0** · Windows 10 / 11 · Yapımcı **TarikPro43391**

T-BOOSTER, Windows için Türkçe bir performans ve sistem bakım uygulamasıdır. Donanım kullanımını izleyebilir, oyun ayarlarını yönetebilir, disk sağlığını inceleyebilir ve bakım araçlarına tek pencereden erişebilirsin.

## Kurulum ve başlatma

1. ZIP dosyasının tamamını bir klasöre çıkar.
2. Windows’ta **Tkinter destekli Python 3.10 veya üzeri** kurulu olmalı.
3. Çıkardığın klasörden [`t-booster.bat`](t-booster.bat) dosyasını aç. Uygulama, sistem ayarlarına erişmek için Windows yönetici izni ister.

Masaüstü kısayolu oluşturmak için [`T_BOOSTER_KISAYOL_OLUSTUR.bat`](T_BOOSTER_KISAYOL_OLUSTUR.bat) dosyasını çalıştırabilirsin. Terminalden başlatmak için uygulama klasöründe `python T_BOOSTER_V1_1_0.py` komutunu kullan.

## v1.1.0

- Yükleme adımlarını gösteren açılış animasyonu ve **Uygulama ve Krediler** ekranı.
- Açık ve koyu temalar, mavi butonlar ve yüksek DPI için yuvarlak, animasyonlu **Açık / Kapalı** anahtarları.
- Yan menü kartlarında, Araç Kutusu sekmelerinde ve sağlık puanı halkasında pürüzsüz kenarlar.

| Özellik | Nereden kullanılır? |
| --- | --- |
| Sayfa arama | Sol menüde **Sayfa ara** veya `Ctrl+K`. Sayfa adını yazıp `Enter` ile aç. |
| Tweak profilleri | **Uygulama ve Krediler → Tweak profilleri**. Seçimlerini JSON olarak kaydet veya yükle. Profil yükleme, anahtar seçimlerini günceller. Seçimleri sisteme uygulamak için **Seçili Ayarları Uygula** düğmesini kullan. |
| Sistem özetini kopyalama | **Uygulama ve Krediler → Sistem özetini kopyala**. Windows, işlemci, anakart, BIOS, ekran kartı, bellek ve depolama bilgilerini panoya alır. |
| Pencereyi en üstte tutma | **Uygulama ve Krediler → En üstte tut**. |
| İşlem günlüğünü dışa aktarma | **İşlem Günlüğü → Günlüğü dışa aktar**. Günlüğü bir TXT dosyası olarak kaydeder. |

<details>
<summary>Küçük bir sürpriz ♥</summary>

Sol üstteki T-BOOSTER logosuna bir kez tıkla. Asya için saklanan mesaj orada.

</details>

## Performans ve donanım

- **Kontrol Merkezi** · Canlı CPU, GPU, RAM ve disk kullanımı. **Gerçek FPS Modu**, **Akıllı Boost** ve **Ultra Boost MAX** profillerine erişim.
- **Oyun Modu ve Windows Ayarları** · Oyun ve Windows seçenekleri ile **200 Tweak Paketi**.
- **Sistemi Tara ve Disk Info** · Monitörler, algılanan oyunlar, sistem kontrolleri ve desteklenen sürücüler için SMART bilgileri.
- **Sürücü Merkezi ve FPS LAB** · Donanıma göre üretici destek sayfaları ve PresentMon ile önce/sonra FPS karşılaştırması.
- **Geri Alma Merkezi** · T-BOOSTER’ın yedeklediği sistem ayarlarını geri yükleme.

## Araç Kutusu

26 araç beş sekmede toplanır.

| Sekme | Araçlar |
| --- | --- |
| **Bakım** | Sistem sağlık puanı, geçici dosya temizliği, gizlilik temizliği, geri yükleme noktası, hızlı sorun giderici |
| **Disk & Dosya** | Büyük ve yinelenen dosyaları bulma, klasör boyutu analizi, disk optimizasyonu, dosya karması |
| **Performans** | Arka plan uygulamaları, başlangıç uygulamaları, güç planları, pil sağlığı, yüklü programlar |
| **Ağ** | DNS ve ağ araçları, internet hız testi, açık bağlantılar, yerel ağdaki cihazlar, ping ve yol izleme |
| **Güvenlik & Sistem** | Kayıtlı Wi-Fi bilgileri, SFC, hosts denetimi, olay günlüğü, zamanlanmış görevler, Windows güncelleme geçmişi |

Sistem ayarı uygulamadan önce **Araç Kutusu → Bakım → Geri Yükleme Noktası** aracını kullanabilirsin.

## Proje dosyaları

| Dosya | Görevi |
| --- | --- |
| [`T_BOOSTER_V1_1_0.py`](T_BOOSTER_V1_1_0.py) | Ana uygulama ve arayüz |
| [`tb_release_ui.py`](tb_release_ui.py) | Açılış ekranı, sayfa arama ve uygulama araçları |
| [`tb_core.py`](tb_core.py) | Sistem bilgileri, yedekleme ve geri yükleme |
| [`tb_features.py`](tb_features.py), [`tb_tools.py`](tb_tools.py), [`tb_suite.py`](tb_suite.py) | Araç Kutusu, oyun ve performans modülleri |

T-BOOSTER [MIT lisansı](LICENSE) ile yayımlanır.
