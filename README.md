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

## Testler

```
python test_engine.py
```

## Derleme (Windows .exe / macOS .app)

GitHub Actions `release` workflow'u `v*` etiketlerinde otomatik derler:

- **Windows x64** → `LNG-Orifice-Meter.exe`
- **macOS Apple Silicon (arm64, M1 Pro uyumlu)** → `.app.zip`

Yerel derleme:

```
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean --windowed --onefile --name "LNG-Orifice-Meter" main.py
```

## Uyarı

Bu araç ön tasarım ve fizibilite içindir. Resmî ölçüm noktası tasarımı; kalibrasyon, montaj, legal metroloji onayı ve sahaya özel düz boru/bağlantı değerlendirmesi gerektirir.