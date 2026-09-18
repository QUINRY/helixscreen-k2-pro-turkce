# HelixScreen Türkçe v1.0.0-tr.1

Creality K2 Pro için HelixScreen 1.0.0 tabanlı Türkçe sürüm.

Taban sürümün değişiklikleri: [HelixScreen v1.0.0](https://github.com/prestonbrown/helixscreen/releases/tag/v1.0.0)

## Öne çıkanlar

- Dil menüsünden seçilebilen UTF-8 Türkçe arayüz
- Güncel K2 paketinin İngilizce kaynaklarına göre 2.868 çevrilmiş metin
- CFS destekli ekranlar ve çoklu filament yönetimi
- Mevcut HelixScreen 1.0.0 için ayarları koruyan geri alınabilir katman
- Resmî güncellemeden kalan eski Türkçe işaretini algılayıp 1.0.0 için yeni ve temiz geri dönüş yedeği oluşturma
- HelixScreen kurulu olmayan K2 Pro için tam kurulum paketi
- Baskı durumu, mimari ve SHA-256 güvenlik kontrolleri
- Tek komutla kurma, güncelleme ve kaldırma
- Dokunmatik/CFS ayarlarının korunması, kurma-kaldırma, servis hatasında geri dönüş ve bozuk paket/sürüm reddi geçici dosya sisteminde sınandı
- Mevcut dokuz dil korunur; Türkçe onuncu dil olarak eklenir
- K2/ARMv7 hedefi için kaynak koddan derlenir; Snapmaker U1 ikilisi kullanılmaz

## Paketler

- `helixscreen-k2-tr-overlay.zip`: HelixScreen 1.0.0 zaten kuruluysa önerilen küçük paket.
- `helixscreen-k2.zip`: HelixScreen kurulu olmayan K2 Pro için tam paket.
- `SHA256SUMS`: İndirilen paketleri bağımsız doğrulamak için özetler.
- `install.sh` / `remove.sh`: İncelemek veya çevrimdışı kullanmak isteyenler için kurucu ve kaldırıcı.

Kurucu yazıcının mevcut durumunu algılar ve doğru paketi otomatik indirir. Ayrıntılı komutlar ve ekran görüntüleri için depo ana sayfasına bakın.

## Doğrulama

- [K2 kaynak derlemesi başarıyla tamamlandı](https://github.com/QUINRY/helixscreen-k2-pro-turkce/actions/runs/35379223498): statik bağlı 32 bit ARM/EABI5.
- Çeviri üretimi, yer tutucular, Türkçe font kapsamı, 10 dilin seçim sırası ve kurucu için **134 yerel test** geçti.
- Üç hata senaryosunda koruma kodu bilinçli olarak devre dışı bırakıldığında ilgili testlerin başarısız olduğu doğrulandı.
- Güncellemeden kalmış eski Türkçe yedeğinin farklı bir taban sürümüne geri yüklenmesi engellenir.

Bu kontroller fiziksel cihaz testi değildir.

**0.99.x'ten yükseltme:** Önce resmî HelixScreen **1.0.0 K2** paketine güncelleyin, ardından bu projenin Türkçe kurulum komutunu çalıştırın. 1.0.0 Türkçe katmanı eski tabana kurulmaz. Eski sürümler silinmemiştir.

> **Bu yeni 1.0.0 Türkçe paket fiziksel K2 Pro üzerinde henüz denenmemiştir.** Önceki 0.99.118 donanım testi bu sürüm için test iddiası değildir. Yazıcıya uzaktan kurulum yapılmamıştır. Root/SSH açık olmalı ve yazıcı baskı yapmıyor olmalıdır.

Asıl HelixScreen geliştirmesi [Preston Brown ve katkıcılarına](https://github.com/prestonbrown/helixscreen) aittir. Bu ücretsiz topluluk paketi Türkçe yerelleştirme ekler; Creality'nin resmî ürünü değildir. Kaynak kod ve değişiklikler GPL-3.0-or-later kapsamındadır.
