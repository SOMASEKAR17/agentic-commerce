import uuid
from app.db import get_conn, init_db

PRODUCTS = [
    # =========================================================================
    # 1. AUDIO & SOUND ACCESSORIES (20 items)
    # =========================================================================
    ("Sony WH-CH520 Wireless Headphones", "Wireless, noise isolation, 50h battery", 4500, 4.5, 3200),
    ("boAt Rockerz 450", "Wireless, bass boost, 15h battery", 1800, 4.2, 9800),
    ("JBL Tune 510BT", "Wireless, lightweight, 40h battery", 2200, 4.4, 5600),
    ("Sennheiser HD 350BT", "Wireless, ANC, 30h battery", 4900, 4.6, 1200),
    ("Protective Headphone Case", "Hard shell carrying case", 400, 4.1, 500),
    ("Boult Audio ProBass Curve", "Wireless neckband, ANC", 1500, 4.0, 4400),
    ("Sony WH-1000XM5", "Flagship active noise cancelling over-ear headphones", 26990, 4.8, 5400),
    ("Apple AirPods Pro (2nd Gen)", "ANC, transparency mode, adaptive audio, USB-C", 20990, 4.7, 8200),
    ("Bose QuietComfort 45", "Premium over-ear noise cancelling headphones", 22900, 4.6, 3100),
    ("JBL Flip 6 Portable Bluetooth Speaker", "IP67 waterproof, 12h playtime, PartyBoost", 9999, 4.6, 11400),
    ("Marshall Emberton II", "Compact portable stereo speaker, 30+ hours battery", 14999, 4.7, 2400),
    ("Nothing Ear (a)", "Yellow design, 45dB ANC, Hi-Res wireless audio", 7999, 4.4, 1850),
    ("OnePlus Bullets Wireless Z2", "Bass edition, magnetic controls, fast charging", 1799, 4.3, 14200),
    ("Realme Buds Air 5 Pro", "Dual drivers, 50dB active noise cancellation", 4999, 4.4, 3800),
    ("Audio-Technica ATH-M50x", "Professional studio monitor wired headphones", 11990, 4.7, 7300),
    ("Tribit StormBox Micro 2", "Rugged pocket speaker with bike mount strap", 3999, 4.5, 1900),
    ("Soundcore by Anker Life Q30", "Hybrid active noise cancelling headphones", 6999, 4.5, 4100),
    ("Fiio JadeAudio KA1 DAC", "USB-C to 3.5mm hi-fi headphone amplifier", 3499, 4.6, 620),
    ("SpinFit CP100 Plus Eartips", "Medical grade silicone replacement tips pack", 899, 4.4, 870),
    ("Shure MV7 USB Microphone", "Dynamic podcast microphone for voice and streaming", 19999, 4.8, 1450),

    # =========================================================================
    # 2. WEARABLES & SMART DEVICES (20 items)
    # =========================================================================
    ("Amazfit GTS 4 Mini Smartwatch", "1.65-inch AMOLED display, GPS, 15-day battery", 7999, 4.3, 1850),
    ("Noise ColorFit Pulse 2 Max", "1.85-inch display, Bluetooth calling, 550 nits", 1999, 4.1, 8400),
    ("Apple Watch SE (2nd Gen)", "Retina display, fitness tracker, crash detection", 24900, 4.7, 6100),
    ("Samsung Galaxy Watch 6", "Super AMOLED, sleep coaching, ECG tracking", 19999, 4.5, 3400),
    ("Garmin Forerunner 55", "GPS running watch with daily suggested workouts", 18490, 4.6, 1200),
    ("Fitbit Charge 6", "Health tracker, built-in GPS, EDA sensor", 13999, 4.2, 2100),
    ("Fire-Boltt Ninja Call Pro Plus", "1.83-inch HD display, AI voice assistant", 1499, 4.0, 16800),
    ("OnePlus Watch 2", "Wear OS by Google, 100h battery life in Smart Mode", 21999, 4.5, 1300),
    ("Amazfit T-Rex 2", "Rugged outdoor GPS smartwatch, 15 military certs", 15999, 4.6, 940),
    ("boAt Wave Call Smartwatch", "Bluetooth calling with dial pad, 1.69-inch screen", 1699, 4.1, 11500),
    ("Titan Smart 3", "1.96-inch AMOLED display, metallic chassis", 5995, 4.3, 1800),
    ("Ultrahuman Ring AIR", "Ultralight titanium smart sleep and metabolism tracker", 24999, 4.4, 480),
    ("Fastrack Limitless FS1", "Single-sync Bluetooth calling, fast processing", 1795, 4.0, 7200),
    ("Realme Watch 3 Pro", "Curved AMOLED screen with multi-system standalone GPS", 3999, 4.3, 4100),
    ("Xiaomi Smart Band 8", "1.62-inch AMOLED display, pebble mode clip support", 3499, 4.4, 2900),
    ("Spigen Rugged Armor Case for Apple Watch", "Shock-absorbent protective frame", 1499, 4.5, 2300),
    ("Ringke Bezel Styling for Galaxy Watch", "Stainless steel protective adhesive ring", 1199, 4.3, 850),
    ("Nylon Loop Strap Pack (20mm)", "Breathable quick-release sport bands set of 3", 699, 4.2, 3100),
    ("Magnetic Silicone Watch Band (22mm)", "Reversible dual-tone magnetic clasp strap", 899, 4.4, 1400),
    ("Armour Screen Protector Pack (Smartwatch)", "Tempered glass guard 4-pack with auto-alignment", 399, 4.1, 4200),

    # =========================================================================
    # 3. SMARTPHONES & MOBILE ACCESSORIES (20 items)
    # =========================================================================
    ("Anker 65W GaN Fast Charger", "Dual USB-C ports, compact fast charging adapter", 2999, 4.7, 2100),
    ("Mi 20000mAh Power Bank 3i", "18W fast charging, triple output ports", 2199, 4.4, 14500),
    ("Spigen Ultra Hybrid Phone Case", "Clear bumper case, shockproof air-cushion tech", 1299, 4.5, 3100),
    ("Samsung Galaxy S23 FE 5G", "8GB RAM, 128GB storage, dynamic AMOLED 120Hz", 39999, 4.3, 5800),
    ("OnePlus Nord CE 3 Lite 5G", "108MP camera, 67W SuperVOOC fast charging", 17499, 4.2, 19200),
    ("Belkin MagSafe Wireless Charger Pad", "15W certified magnetic fast charging puck", 2499, 4.5, 1100),
    ("Baseus 100W USB-C to USB-C Cable", "Braided high durability cable with E-marker chip (2m)", 699, 4.6, 5600),
    ("Ugreen Car Phone Mount", "Air vent gravity clamp holder with 360-degree rotation", 899, 4.3, 3400),
    ("Ambrane 10000mAh Magnetic Power Bank", "MagSafe compatible compact wireless bank with kickstand", 1699, 4.1, 4700),
    ("Spigen GlasTR EZ FIT Screen Protector", "Tempered glass auto-alignment tray 2-pack", 999, 4.7, 9800),
    ("ESR HaloLock Ring Kickstand", "Universal snap-on magnetic phone ring and desk stand", 1099, 4.4, 1900),
    ("Portronics Clamp X Car Mobile Holder", "Dashboard and windshield telescopic suction mount", 599, 4.0, 8300),
    ("Nillkin CamShield Pro Back Cover", "Slide camera lens protector and grooved grip case", 1199, 4.4, 2600),
    ("Stuffcool 33W Dual Port Wall Adapter", "Type C PD and USB A fast charger for iPhone and Android", 1299, 4.3, 3100),
    ("Amazon Basics Lightning to USB Cable", "MFi certified durable braided cable (1m)", 499, 4.2, 12800),
    ("Zagg InvisibleShield Wet Cleaning Kit", "Microfiber cloths and screen cleaning spray set", 449, 4.5, 1300),
    ("Lisen Magnetic Wireless Car Charger", "MagSafe vent mount with 15W Qi fast charging", 2199, 4.4, 760),
    ("SanDisk 128GB Ultra Dual Drive Luxe", "All-metal Type-C and Type-A OTG pen drive", 1149, 4.4, 21400),
    ("Syncwire Waterproof Phone Pouch", "IPX8 dry bag for swimming and underwater photos 2-pack", 599, 4.3, 3900),
    ("Mobile Gaming Finger Sleeves Pack", "Conductive carbon fiber sweat-proof thumb gloves 6-pack", 249, 4.1, 6200),

    # =========================================================================
    # 4. WORKSPACE & COMPUTER ACCESSORIES (20 items)
    # =========================================================================
    ("Logitech MX Master 3S", "Ergonomic wireless mouse, 8K DPI sensor, quiet clicks", 8995, 4.8, 4100),
    ("Keychron K2 V2 Mechanical Keyboard", "Wireless/wired 75% layout, Gateron brown switches", 7499, 4.6, 1400),
    ("BenQ ScreenBar Monitor Light", "Auto-dimming LED desk lamp, glare-free optical design", 9990, 4.7, 850),
    ("Dell 24-inch IPS Monitor (S2421HN)", "Full HD, 75Hz refresh rate, AMD FreeSync, ultra-thin", 10499, 4.4, 6900),
    ("Logitech C920x Pro HD Webcam", "1080p 30fps streaming camera with dual mics", 6495, 4.6, 5300),
    ("Elgato Stream Deck MK.2", "15 customizable LCD keys for studio macro control", 13490, 4.8, 1800),
    ("Rain Design mStand Laptop Stand", "Solid aluminum ergonomic riser for MacBook and laptops", 3999, 4.7, 4400),
    ("Anker 7-in-1 USB-C Hub", "4K HDMI output, 100W power delivery, SD/TF card reader", 3299, 4.5, 3800),
    ("Blue Yeti USB Condenser Microphone", "Tri-capsule array, 4 polar patterns for vocal recording", 9999, 4.5, 8700),
    ("CalDigit TS4 Thunderbolt 4 Dock", "18 expansion ports, 98W charging for multi-display", 36999, 4.8, 420),
    ("HUANUO Dual Monitor Gas Spring Arm", "Adjustable desk mount for twin 17 to 32-inch screens", 4999, 4.4, 2800),
    ("Orbitkey Vegan Leather Desk Mat", "Large writing blotter with magnetic document hideaway", 4299, 4.6, 730),
    ("Kensington ErgoSoft Wrist Rest", "Gel-cushioned keyboard palm support", 1499, 4.3, 1600),
    ("Logitech K380 Multi-Device Keyboard", "Compact Bluetooth typing across 3 paired computers", 2895, 4.5, 9200),
    ("Samsung T7 Shield 1TB Portable SSD", "USB 3.2 Gen 2 up to 1050MB/s rugged external drive", 8999, 4.8, 4900),
    ("SanDisk Extreme 64GB MicroSD Card", "A2, UHS-I, up to 170MB/s read speed for cameras", 699, 4.5, 18200),
    ("Cable Matters Velcro Cable Ties (50pk)", "Reusable self-gripping wire organization straps", 499, 4.6, 7100),
    ("Vented Mesh Metal Laptop Tray", "Foldable 6-angle adjustable cooling riser", 699, 4.2, 5400),
    ("UGREEN Cat 8 Braided Ethernet Cable", "40Gbps 2000MHz flat high-speed gigabit wire (3m)", 599, 4.7, 3600),
    ("Audioengine A2+ Powered Desktop Speakers", "Built-in 24-bit DAC analog studio monitors pair", 24900, 4.7, 910),

    # =========================================================================
    # 5. SMART HOME & HOME APPLIANCES (20 items)
    # =========================================================================
    ("Amazon Echo Dot (5th Gen)", "Smart speaker with Alexa, deeper bass, motion sensor", 4499, 4.4, 11200),
    ("TP-Link Tapo Smart Wi-Fi Plug", "Remote control, voice control with Alexa & Google", 999, 4.3, 4200),
    ("Fire TV Stick 4K Max", "Wi-Fi 6 streaming stick, Dolby Vision & Atmos", 5999, 4.6, 8900),
    ("Philips Daily Collection Air Fryer", "Rapid Air technology, 4.1L capacity, 1400W", 6999, 4.4, 6300),
    ("Morphy Richards Electric Kettle", "1.8L stainless steel body, auto cut-off protection", 1299, 4.2, 5100),
    ("Wacaco Minipresso NS", "Portable manual espresso maker compatible with pods", 4899, 4.5, 920),
    ("Philips Hue Smart LED Bulb (B22)", "16 million colors, Bluetooth and Zigbee compatible", 2299, 4.4, 3800),
    ("Eufy RoboVac 11S", "Slim quiet robot vacuum cleaner, 1300Pa strong suction", 14999, 4.3, 3100),
    ("Dyson Cool AM07 Tower Fan", "Air Multiplier bladeless cooling technology with remote", 31900, 4.6, 1200),
    ("MI Smart Air Purifier 4", "True HEPA filter, laser particle sensor, OLED display", 13999, 4.4, 4600),
    ("Qubo Smart Video Doorbell", "1080p camera, two-way audio, chime included", 5490, 4.1, 1400),
    ("Havells Instanio 3-Litre Instant Geyser", "Stainless steel inner tank, LED color indicator", 3699, 4.3, 8900),
    ("Prestige Iris 750W Mixer Grinder", "3 stainless steel jars, 1 transparent juicer jar", 2999, 4.0, 24100),
    ("Kent Grand Plus Mineral RO Purifier", "RO + UV + UF + TDS water controller 9L storage", 14499, 4.2, 9800),
    ("Nutribullet Pro 900W High Speed Blender", "Nutrient extractor with 2 compact cup attachments", 6999, 4.6, 2100),
    ("Tapo C210 2K Pan/Tilt Home Security Camera", "3MP resolution, motion detection, micro SD storage", 2199, 4.4, 12800),
    ("Bajaj DX-7 1000W Dry Iron", "Non-stick coated soleplate, thermal fuse safety", 799, 4.2, 14700),
    ("Inalsa Stand Mixer & Dough Kneader", "1000W copper motor with 5.5L stainless steel bowl", 6499, 4.3, 1100),
    ("Syska 9W Smart LED Bulb", "Wi-Fi app control with 3 million color transitions", 499, 4.0, 9300),
    ("Godrej Safe Electronic Digital Locker", "Motorized shooting bolts, 10-liter steel lockbox", 4999, 4.2, 3400),

    # =========================================================================
    # 6. GAMING GEAR & CONSOLES (20 items)
    # =========================================================================
    ("Xbox Wireless Controller", "Textured grip, hybrid D-pad, Bluetooth connectivity", 5390, 4.6, 7300),
    ("Razer Gigantus V2 Mousepad", "XXL thick gaming mouse mat with textured micro-weave", 2499, 4.5, 1800),
    ("PlayStation 5 DualSense Controller", "Haptic feedback, adaptive triggers, built-in mic", 5790, 4.7, 8800),
    ("SteelSeries Arctis Nova 7 Wireless", "Multi-platform gaming headset with simultaneous Bluetooth", 17999, 4.5, 1100),
    ("Logitech G502 HERO Gaming Mouse", "25K DPI sensor, 11 programmable buttons, adjustable weights", 3995, 4.6, 12400),
    ("Razer BlackWidow V4 Mechanical Keyboard", "Clicky green switches, multi-function roller wheel", 12999, 4.6, 1700),
    ("HyperX QuadCast S RGB USB Mic", "Anti-vibration shock mount, customizable light zones", 12490, 4.7, 3400),
    ("Nintendo Switch OLED Console", "7-inch vibrant OLED screen, 64GB storage, white dock", 29990, 4.8, 4600),
    ("Turtle Beach Recon 70 Gaming Headset", "Multi-platform wired headset with flip-to-mute mic", 2799, 4.2, 3900),
    ("Corsair MM350 Anti-Fray Cloth Pad", "Extended gaming surface with precision stitched borders", 2199, 4.6, 2900),
    ("Elgato HD60 X External Capture Card", "1080p60 HDR10 capture, 4K60 passthrough with VRR", 16999, 4.7, 890),
    ("Sony PS5 DualSense Charging Station", "Click-in dock charges up to two controllers simultaneously", 2490, 4.8, 3800),
    ("8BitDo Ultimate Bluetooth Controller", "Hall effect joysticks with charging dock and macro keys", 5499, 4.7, 1600),
    ("Razer DeathAdder Essential Wired Mouse", "6400 DPI optical sensor, ergonomic shape 5 buttons", 1199, 4.3, 19400),
    ("Redragon K552 Mechanical Keyboard", "Compact 87-key rainbow backlit dust-proof blue switches", 2499, 4.3, 8700),
    ("Xbox Series X/S Play and Charge Kit", "Rechargeable battery pack with USB-C braided cable", 2190, 4.5, 2300),
    ("Cosmic Byte GS410 Headset with Mic", "Entry-level wired gaming headphone for PC and mobile", 849, 4.0, 11200),
    ("Govee RGBIC Flow Pro LED Light Bars", "Smart camera color-sync ambient backlighting for gaming", 6999, 4.5, 1400),
    ("Thrustmaster T128 Racing Wheel & Pedals", "Force feedback wheel with magnetic pedal set", 19999, 4.4, 520),
    ("PlayStation PULSE 3D Wireless Headset", "Tuned for 3D Audio on PS5 consoles with dual hidden mics", 7990, 4.4, 4300),
]

def seed():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM products")
    for name, desc, price, rating, reviews in PRODUCTS:
        conn.execute(
            "INSERT INTO products (id, name, description, price, rating, reviews, stock, agent_enabled) VALUES (?,?,?,?,?,?,?,1)",
            (str(uuid.uuid4())[:8], name, desc, price, rating, reviews, 50),
        )
    conn.commit()
    conn.close()
    print("Catalog seeded.")

if __name__ == "__main__":
    seed()