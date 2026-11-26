# T-BOOSTER

**v1.1.2** · **Windows 10 / 11** · **Türkçe arayüz** · **TarikPro43391**

T-BOOSTER, Windows için bir performans ve sistem bakım uygulamasıdır. Donanım kullanımını canlı izleyebilir, oyun ayarlarını yönetebilir, disk sağlığını inceleyebilir ve yedeklenen sistem değişikliklerini geri alabilirsin.

## v1.1.2 yenilikleri

- **VPN kategorisi** · Sol menüde **Kontrol Merkezi**’nin hemen altında yer alıyor. **Erişim Engeli Açma** düğmesi, GoodbyeDPI’ın `turkey_dnsredir.cmd` profilini geçici olarak çalıştırıyor. Aynı düğmeye tekrar basınca veya T-BOOSTER kapanınca oturum sona eriyor.
- **Güncellenen logolar** · Kontrol Merkezi’ndeki **Intel Maksimum Performans** kartında Intel logosu görünüyor. Intel, AMD ve NVIDIA logoları yüksek DPI için güncellendi.
- **Her bölüm için ayrı ikon** · Sol menüdeki 15 bölümün kendine ait ikonu var. Kart ve sekmelerin yuvarlak kenarları pürüzsüzleştirildi. Kontrol Merkezi başlıkları dar alanda alt satıra geçiyor.
- **Logoyla uyumlu renkler** · Butonlar ve açık konumdaki anahtarlar, T-BOOSTER logosundan alınan koyu mavi `#1B4F8F` tonunu kullanıyor. Açık ve koyu tema seçenekleri bulunuyor.

## Kurulum

**Gereksinimler** · Windows 10 veya 11 ve Tkinter içeren Python 3.10 veya üzeri.

1. `T-BOOSTER-v1.1.2.zip` dosyasının tamamını bir klasöre çıkar.
2. Çıkardığın klasörde `t-booster.bat` dosyasını aç.
3. Windows yönetici izni istediğinde onayla.

Terminalden başlatmak için uygulama klasöründe şu komutu çalıştırabilirsin.

```powershell
python T_BOOSTER_V1_1_2.py
```

Masaüstü kısayolu için `T_BOOSTER_KISAYOL_OLUSTUR.bat` dosyasını kullan.

## Özellikler

| Bölüm | Neler yapabilirsin? |
| --- | --- |
| **Kontrol Merkezi** | CPU, GPU, RAM ve disk kullanımını izle. Akıllı Boost, Ultra Boost MAX ve oyun odaklı ayarlara eriş. |
| **Oyun Modu ve Windows Ayarları** | Oyun ve Windows seçeneklerini yönet. **200 Tweak Paketi** içinden uygulamak istediğin ayarları seç. |
| **Disk Info ve Sistemi Tara** | Desteklenen disklerde SMART verilerini, monitörleri ve algılanan oyunları incele. |
| **FPS LAB** | PresentMon ile değişiklik öncesi ve sonrası FPS ölçümlerini karşılaştır. |
| **Araç Kutusu** | Bakım, disk ve dosya, performans, ağ, güvenlik ve sistem kategorilerinde toplam 26 araca eriş. |
| **Geri Alma Merkezi** | T-BOOSTER’ın yedeklediği sistem ayarlarını geri yükle. |

### Günlük kullanım

- **`Ctrl+K`** ile sayfa ara ve **`Enter`** ile aç.
- **Uygulama ve Krediler** ekranında tweak seçimlerini JSON profili olarak kaydet veya yükle, sistem özetini panoya kopyala ya da pencereyi en üstte tut.
- **İşlem Günlüğü → Günlüğü dışa aktar** ile işlemleri TXT dosyası olarak kaydet.

Sistem ayarlarını değiştirmeden önce **Araç Kutusu → Bakım → Geri Yükleme Noktası** aracını kullanabilirsin.

<details>
<summary>Asya için küçük bir sürpriz ♥</summary>

Uygulamanın sol üstündeki T-BOOSTER logosuna bir kez tıkla.

</details>

## Yapımcı ve lisans

**TarikPro43391**

T-BOOSTER, MIT lisansıyla yayımlanır. GoodbyeDPI ve beraberindeki bileşenlerin lisansları paketteki `goodbyedpi/licenses/` klasöründedir.
