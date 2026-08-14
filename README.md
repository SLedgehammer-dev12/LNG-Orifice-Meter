# LNG Orifis Ölçüm Noktası Tasarım Aracı

Kriyojenik LNG hatlarında **orifis ölçüm noktası boyutlandırması** için ISO 5167-2, Peng-Robinson EOS, Revised Klosek-Zander ve ASME B31.3 tabanlı, GC/DCS beslemeli mol bileşimine göre hesaplama yapan bir masaüstü + komut satırı aracı.

## Özellikler

- **Dinamik termofiziksel hesap:** Mol bileşiminden (CH₄, C₂H₆, C₃H₈, i-C₄, n-C₄, i-C₅, n-C₅, N₂) çalışma yoğunluğu ve doymuş buhar basıncı.
  - Bubble point: **Peng-Robinson EOS** (fugasite katsayısı yöntemi) — birincil
  - Karşılaştırma: Antoine + Raoult — ikincil
  - Yoğunluk: **Revised Klosek-Zander** (Rackett sıcaklığa bağlı molar hacimler + MW bağımlı düzeltme)
- **Kriyojenik termal büzülme:** AISI 304/316 için soğuk çalışma çapları (D_T, d_T) ve imalat çapı (d₂₀).
- **ISO 5167-2 boyutlandırma:** Tam Reader-Harris/Gallagher (flange taps) deşarj katsayısı, Newton-Raphson çözücü (bisection yedekli), akış belirsizliği.
- **Emniyet denetimi:** Flashing/kavitasyon (boru sürtünme kaybı dahil), Pvc/vena contracta, ASME B31.3 minimum et kalınlığı.
- **N₂ duyarlılık analizi** ve açıklayıcı HTML raporu.
- **Güncelleme kontrolü:** GitHub Releases üzerinden en son sürümü otomatik (açılışta)
  ve manuel (GUI butonu / CLI bayrağı) kontrol eder; yeni sürümü indirme yardımcısı.

## Gereksinim

- Python 3.10+ (Tkinter dahil: macOS'ta sistem Pythonomu, Windows'ta python.org kurulumu gömülü gelir)

## Kullanım

Masaüstü arayüzü:

```
python main.py
```

Komut satırı (BOTAŞ varsayılan örneği):

```
python main.py --cli
python main.py --cli --qm 200 --dp 300 --qmin 25 --qmax 130 --out rapor.html --json sonuc.json
```

Parametreler: `--t1 --p1 --d20 --qm --dp --qmin --qmax --L --od --t --comp --out --json --no-html`

Bileşim: `--comp "CH4:0.915,C2H6:0.055,C3H8:0.018,iC4:0.004,nC4:0.004,iC5:0.001,nC5:0.001,N2:0.002"`

Güncelleme kontrolü / indirme:

```
python main.py --check-updates   # en son sürümü kontrol eder (GUI başlatmaz)
python main.py --update          # en son sürümü ~/Downloads'a indirir ve klasörde açar
```

## Testler

```
python test_engine.py
```

## Derleme (Windows .exe / macOS .app)

GitHub Actions `release` workflow'u `v*` etiketlerinde otomatik derler:

- **Windows x64** → `LNG-Orifice-Meter-windows-x64.exe`
- **macOS Apple Silicon (arm64, M1 Pro uyumlu)** → `.app.zip`

**Neden Nuitka?** Yapılar PyInstaller ile değil, **Nuitka** (C'ye derleyen) ile üretilir.
PyInstaller `--onefile` bootloader'ı (belleğe açılan kendi kendine paket) antivirüs
heuristiklerinde popüler bir yanlış pozitif kaynağıdır. Nuitka gerçek makine kodu üretir;
bu, AV uyarılarını önemli ölçüde azaltır. Ayrıca yapılara doğru ürün/sürüm meta verisi
eklenir (Windows PE) ve macOS'ta ad-hoc kod imzası atılır.

Yerel derleme:

```
pip install -r requirements-build.txt
# Windows:
python -m nuitka --standalone --onefile --enable-plugin=tk-inter --windows-console-mode=disable --output-filename="LNG-Orifice-Meter" main.py
# macOS (.app):
python -m nuitka --standalone --enable-plugin=tk-inter --macos-create-app-bundle --macos-app-mode=gui main.py
```

## Güvenlik / Antivirüs Uyarıları

İmzasız ikili dosyalar her zaman bazı antivirüs/Gatekeeper heuristiklerine takılabilir.
Bunun gerçek ve kalıcı çözümü, **ticari kod imzası** gerektirir:

- **Windows (SmartScreen):** Microsoft Authenticode sertifikası ile sağlanan imza,
  SmartScreen uyarısını kaldırır. Sertifika yıllık ücretlidir.
- **macOS (Gatekeeper):** Apple Developer ID sertifikası + **notarization** gerekir
  (yıllık Apple Developer programı).

Bunlar olmadan sürüm güvenilirliğini aşağıdaki gibi sağlamlaştırıyoruz:

1. **Doğal kod derleme (Nuitka)** — bootloader/açılma noktası yerine gerçek makine kodu.
2. **Windows PE meta verisi** — dosya açıklaması, sürüm, şirket adı.
3. **macOS ad-hoc imza** — bütünlük doğrulama imkânı; `spctl` Gatekeeper'ı yine de
   engeller (imzalanmamış/notarize edilmemiş indirmelerde).

**Güvenli çalıştırma adımları:**

- İndirmeyi yalnızca resmî **Releases** sayfasından yapın; indirdiğiniz dosyanın
  SHA-256 özetini kontrol edin.
- **Windows:** `SmartScreen → More info → Run anyway`; sonraki açılışlarda uyarı çıkmaz.
- **macOS:** Sağ tık (veya Control+tık) → **Aç**, ardından "Aç" seçeneğine tıklayın.
  Kalıcı çözüm: `xattr -dr com.apple.quarantine "/indirilen yol/LNG-Orifice-Meter.app"`.
- Kaynak koddan da çalıştırabilirsiniz: `python main.py` (bu yolda ikili doğrulama
  gereksinimi yoktur).

Her sürümün yapıtları GitHub Actions'ta aynı kaynaktan derlenir; bir AV raporu alırsanız
repo **Issues**'a bildirin.

## Uyarı

Bu araç ön tasarım ve fizibilite içindir. Resmî ölçüm noktası tasarımı; kalibrasyon, montaj, legal metroloji onayı ve sahaya özel düz boru/bağlantı değerlendirmesi gerektirir.