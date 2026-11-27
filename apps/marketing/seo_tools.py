"""Content of the free QR generator landing pages (English and Azerbaijani).

Each page serves its own search intent: a specific QR type with its own instructions,
examples and FAQs. Titles, descriptions and H1s can be overridden in the admin (Page SEO).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    slug: str            # URL: /<slug>/
    type_key: str        # generator type preselected on the page
    icon: str
    related: tuple       # slugs of related tools
    content: dict        # {"en": {...}, "az": {...}}

    @property
    def url_name(self) -> str:
        return "tool_" + self.slug.replace("-", "_")


def _c(title, description, h1, intro, steps, uses, example, faq, link_label):
    return {"title": title, "description": description, "h1": h1, "intro": intro,
            "steps": steps, "uses": uses, "example": example, "faq": faq,
            "link_label": link_label}


TOOLS = [
    Tool("qr-code-generator", "url", "qr",
         ("url-qr-code-generator", "wifi-qr-code-generator", "whatsapp-qr-code-generator",
          "vcard-qr-code-generator"), {
        "en": _c(
            "QR Code Generator – Free, No Signup | Qrumy",
            "Make a QR code for a link, WiFi, WhatsApp, phone, email, SMS, location or contact "
            "card. Pick a style, add a logo and download PNG or SVG — free.",
            "QR Code Generator",
            "Choose what the code should do, fill in one or two fields and download a "
            "print-ready QR code. Static codes are free forever and work without Qrumy.",
            ["Choose the type: website, WiFi, text, phone, SMS, email, WhatsApp, location or "
             "contact card.", "Fill in the fields — the preview updates as you type and is "
             "test-scanned automatically.", "Pick a pattern, corner style, colours, frame and "
             "logo, then download PNG for screens or SVG for print."],
            ["Posters, flyers and shop windows", "Restaurant tables and receipts",
             "Business cards and email signatures", "Product packaging and labels"],
            "A bakery prints a QR code with its Instagram link on paper bags and a WiFi QR "
            "code on each table, so guests connect without asking for the password.",
            [("Is this QR code generator really free?", "Yes. Static QR codes are free, "
              "without an account, a watermark or a scan limit."),
             ("Do the codes expire?", "Static codes never expire: the content is stored in "
              "the pattern itself and does not depend on our servers."),
             ("PNG or SVG — which should I download?", "PNG (1024 px) is best for websites "
              "and documents. SVG is a vector file that stays sharp at any size, ideal for "
              "print."),
             ("Can I change a code after printing?", "Not a static one. If the link may "
              "change or you want scan statistics, create a free dynamic QR code in your "
              "Qrumy account.")],
            "QR Code Generator"),
        "az": _c(
            "QR Kod Generatoru – Pulsuz, Qeydiyyatsız | Qrumy",
            "Link, Wi-Fi, WhatsApp, telefon, e-poçt, SMS, məkan və ya vizit kartı üçün QR kod "
            "yaradın. Dizayn seçin, loqo əlavə edin, PNG və ya SVG yükləyin — pulsuz.",
            "QR Kod Generatoru",
            "Kodun nə edəcəyini seçin, bir-iki sahəni doldurun və çapa hazır QR kodu "
            "yükləyin. Statik kodlar həmişəlik pulsuzdur və Qrumy-dən asılı olmadan işləyir.",
            ["Növü seçin: veb sayt, Wi-Fi, mətn, telefon, SMS, e-poçt, WhatsApp, məkan və ya "
             "vizit kartı.", "Sahələri doldurun — önizləmə yazdıqca yenilənir və avtomatik "
             "test skanından keçir.", "Naxış, künc forması, rənglər, çərçivə və loqo seçin, "
             "sonra ekran üçün PNG, çap üçün SVG yükləyin."],
            ["Posterlər, bukletlər və vitrinlər", "Restoran masaları və çeklər",
             "Vizit kartları və e-poçt imzaları", "Məhsul qablaşdırması və etiketləri"],
            "Çörəkxana kağız paketlərinə Instagram linki olan QR kod, masalara isə Wi-Fi QR "
            "kodu çap edir — qonaqlar şifrəni soruşmadan qoşulur.",
            [("Bu QR kod generatoru həqiqətən pulsuzdur?", "Bəli. Statik QR kodlar hesabsız, "
              "su nişanı və skan limiti olmadan pulsuzdur."),
             ("Kodların müddəti bitir?", "Statik kodların müddəti bitmir: məzmun naxışın "
              "özündə saxlanılır və serverlərimizdən asılı deyil."),
             ("PNG, yoxsa SVG yükləməliyəm?", "PNG (1024 px) sayt və sənədlər üçün idealdır. "
              "SVG istənilən ölçüdə kəskin qalan vektor fayldır, çap üçün ən yaxşısıdır."),
             ("Çapdan sonra kodu dəyişə bilərəm?", "Statik kodu yox. Link dəyişə bilərsə və "
              "ya skan statistikası lazımdırsa, Qrumy hesabınızda pulsuz dinamik QR kod "
              "yaradın.")],
            "QR kod generatoru"),
    }),
    Tool("url-qr-code-generator", "url", "globe",
         ("qr-code-generator", "whatsapp-qr-code-generator", "text-qr-code-generator"), {
        "en": _c(
            "URL QR Code Generator – Link to Any Website Free | Qrumy",
            "Turn any web address into a QR code. Paste a link like example.com, style the "
            "code and download PNG or SVG for free — no registration needed.",
            "URL QR Code Generator",
            "Paste a website address and get a QR code that opens it on any phone camera. "
            "You can type just “example.com” — https:// is added for you.",
            ["Paste the link of your website, menu, online shop, form or video.",
             "Check the preview — the code is test-scanned before you download it.",
             "Download PNG or SVG and test it with your phone before printing."],
            ["Link a flyer to a landing page or offer", "Open your online menu or price list",
             "Send people to a booking or registration form", "Share a YouTube video or "
             "Google Drive file"],
            "An estate agent puts a URL QR code on every “For sale” sign, linking to the "
            "photos and price of that flat.",
            [("Will the QR code still work if my website changes?", "A static URL QR code "
              "always opens exactly the address it contains. If the page moves, you need a "
              "new code — or use a dynamic QR code whose link you can edit after printing."),
             ("Can I use long links with tracking parameters?", "Yes, but long links make "
              "denser codes. A dynamic code keeps the pattern small and simple."),
             ("Does it work with Instagram or TikTok links?", "Yes, any https link works. "
              "For several links on one page, use a multi-link page in Qrumy.")],
            "URL / website QR"),
        "az": _c(
            "URL QR Kod Generatoru – Sayt Linki üçün Pulsuz QR | Qrumy",
            "İstənilən veb ünvanı QR koda çevirin. example.com kimi linki yapışdırın, dizayn "
            "seçin və PNG və ya SVG-ni pulsuz yükləyin — qeydiyyat lazım deyil.",
            "URL QR Kod Generatoru",
            "Sayt ünvanını yapışdırın və istənilən telefon kamerası ilə açılan QR kod alın. "
            "Sadəcə “example.com” yaza bilərsiniz — https:// avtomatik əlavə olunur.",
            ["Saytınızın, menyunuzun, onlayn mağazanızın, formanızın və ya videonuzun "
             "linkini yapışdırın.", "Önizləməyə baxın — kod yükləməzdən əvvəl test "
             "skanından keçir.", "PNG və ya SVG yükləyin və çapdan əvvəl telefonla yoxlayın."],
            ["Bukletdən kampaniya səhifəsinə keçid", "Onlayn menyu və ya qiymət siyahısı",
             "Rezervasiya və ya qeydiyyat forması", "YouTube videosu və ya Google Drive "
             "faylı"],
            "Daşınmaz əmlak agenti hər “Satılır” lövhəsinə həmin mənzilin şəkilləri və "
            "qiyməti olan səhifəyə aparan URL QR kodu qoyur.",
            [("Saytım dəyişsə, QR kod işləyəcək?", "Statik URL QR kod həmişə içindəki "
              "ünvanı açır. Səhifə köçərsə, yeni kod lazımdır — və ya linki çapdan sonra "
              "dəyişə biləcəyiniz dinamik QR koddan istifadə edin."),
             ("İzləmə parametrli uzun linklərdən istifadə edə bilərəm?", "Bəli, amma uzun "
              "linklər daha sıx kod yaradır. Dinamik kod naxışı kiçik və sadə saxlayır."),
             ("Instagram və ya TikTok linkləri ilə işləyir?", "Bəli, istənilən https link "
              "işləyir. Bir səhifədə bir neçə link üçün Qrumy-də multi-link səhifəsindən "
              "istifadə edin.")],
            "URL / sayt QR"),
    }),
    Tool("wifi-qr-code-generator", "wifi", "wifi",
         ("qr-code-generator", "text-qr-code-generator", "location-qr-code-generator"), {
        "en": _c(
            "WiFi QR Code Generator – Share Your WiFi Password | Qrumy",
            "Create a WiFi QR code so guests join your network by scanning — no typing the "
            "password. Works on iPhone and Android. Free PNG and SVG download.",
            "WiFi QR Code Generator",
            "Enter your network name and password once. Guests point their camera at the "
            "code and connect — handy for cafés, offices, hotels and home.",
            ["Type the network name (SSID) exactly as it appears on your phone.",
             "Choose the security type (usually WPA/WPA2/WPA3) and enter the password.",
             "Download the code and place it where guests can see it — a table tent, the "
             "reception desk or the fridge."],
            ["Cafés and restaurants", "Hotel rooms and guesthouses", "Office meeting rooms",
             "Home guest network"],
            "A café prints “Free WiFi — scan me” table cards. Staff no longer spell out the "
            "password dozens of times a day.",
            [("Do iPhones and Android phones support WiFi QR codes?", "Yes. The built-in "
              "camera on iOS 11+ and modern Android phones shows a “Join network” prompt."),
             ("Is my password stored by Qrumy?", "No. The free generator does not save "
              "anything: the network details exist only inside the QR code you download."),
             ("What if I change the WiFi password?", "Create a new code with the new "
              "password and replace the printed one."),
             ("My network is hidden. Does it still work?", "Yes — tick “Hidden network” so "
              "phones know to look for it.")],
            "WiFi QR"),
        "az": _c(
            "Wi-Fi QR Kod Generatoru – Wi-Fi Şifrəsini QR ilə Paylaşın | Qrumy",
            "Qonaqlar şifrə yazmadan, sadəcə skan edərək şəbəkənizə qoşulsun. iPhone və "
            "Android-də işləyir. PNG və SVG yükləmə pulsuzdur.",
            "Wi-Fi QR Kod Generatoru",
            "Şəbəkə adını və şifrəni bir dəfə daxil edin. Qonaqlar kameranı koda tutur və "
            "qoşulur — kafe, ofis, otel və ev üçün rahatdır.",
            ["Şəbəkə adını (SSID) telefonunuzda göründüyü kimi dəqiq yazın.",
             "Təhlükəsizlik növünü (adətən WPA/WPA2/WPA3) seçin və şifrəni daxil edin.",
             "Kodu yükləyin və qonaqların görəcəyi yerə qoyun — masa kartı, qəbul masası və "
             "ya soyuducu."],
            ["Kafe və restoranlar", "Otel otaqları və qonaq evləri", "Ofis görüş otaqları",
             "Evdə qonaq şəbəkəsi"],
            "Kafe “Pulsuz Wi-Fi — skan et” masa kartları çap edir. İşçilər artıq gündə "
            "onlarla dəfə şifrəni hərf-hərf demir.",
            [("iPhone və Android Wi-Fi QR kodları dəstəkləyir?", "Bəli. iOS 11+ və müasir "
              "Android telefonların kamerası “Şəbəkəyə qoşul” təklifi göstərir."),
             ("Qrumy şifrəmi saxlayır?", "Xeyr. Pulsuz generator heç nə saxlamır: şəbəkə "
              "məlumatları yalnız yüklədiyiniz QR kodun içindədir."),
             ("Wi-Fi şifrəsini dəyişsəm nə olacaq?", "Yeni şifrə ilə yeni kod yaradın və "
              "çap olunmuş kodu dəyişin."),
             ("Şəbəkəm gizlidir. Yenə işləyəcək?", "Bəli — telefonların onu axtarması üçün "
              "“Gizli şəbəkə” qutusunu işarələyin.")],
            "Wi-Fi QR"),
    }),
    Tool("email-qr-code-generator", "email", "mail",
         ("phone-qr-code-generator", "sms-qr-code-generator", "vcard-qr-code-generator"), {
        "en": _c(
            "Email QR Code Generator – Pre-filled Email | Qrumy",
            "Create a QR code that opens a new email with the address, subject and message "
            "already filled in. Free, no signup, PNG and SVG download.",
            "Email QR Code Generator",
            "Scanning the code opens the phone's mail app with your address — and, if you "
            "like, a subject and message — ready to send.",
            ["Enter the email address that should receive the messages.",
             "Optionally add a subject and a short pre-filled message.",
             "Download the code and test it with your phone's mail app."],
            ["Customer support and complaints", "Requesting a quote or catalogue",
             "Event RSVPs and registrations", "Feedback on a product label"],
            "A furniture shop adds an email QR code “Ask for a quote” to its showroom price "
            "tags with the product name already in the subject.",
            [("Which apps open the email?", "The phone's default mail app — Gmail, Outlook, "
              "Apple Mail and others."),
             ("Is the email sent automatically?", "No. The message is only prepared; the "
              "person reviews it and taps Send."),
             ("Can I collect answers in a form instead?", "Yes — Qrumy Surveys gives you a "
              "mobile form with answers in one place, scored and exportable.")],
            "Email QR"),
        "az": _c(
            "E-poçt QR Kod Generatoru – Hazır E-məktub | Qrumy",
            "Ünvanı, mövzusu və mətni əvvəlcədən doldurulmuş yeni e-məktub açan QR kod "
            "yaradın. Pulsuz, qeydiyyatsız, PNG və SVG yükləmə.",
            "E-poçt QR Kod Generatoru",
            "Kodu skan etdikdə telefonun poçt tətbiqi ünvanınızla — istəsəniz mövzu və "
            "mətnlə — göndərməyə hazır açılır.",
            ["Məktubları alacaq e-poçt ünvanını daxil edin.",
             "İstəsəniz mövzu və qısa hazır mətn əlavə edin.",
             "Kodu yükləyin və telefonunuzun poçt tətbiqi ilə yoxlayın."],
            ["Müştəri dəstəyi və şikayətlər", "Qiymət təklifi və ya kataloq sorğusu",
             "Tədbirə qeydiyyat və təsdiq", "Məhsul etiketində rəy"],
            "Mebel mağazası sərgi salonundakı qiymət etiketlərinə mövzusunda məhsulun adı "
            "yazılmış “Qiymət təklifi istə” e-poçt QR kodu əlavə edir.",
            [("E-məktub hansı tətbiqdə açılır?", "Telefonun əsas poçt tətbiqində — Gmail, "
              "Outlook, Apple Mail və başqaları."),
             ("Məktub avtomatik göndərilir?", "Xeyr. Məktub yalnız hazırlanır; insan onu "
              "yoxlayır və Göndər düyməsini basır."),
             ("Cavabları formada toplaya bilərəm?", "Bəli — Qrumy Sorğular cavabları bir "
              "yerdə toplayan, qiymətləndirən və ixrac edən mobil forma verir.")],
            "E-poçt QR"),
    }),
    Tool("phone-qr-code-generator", "phone", "phone",
         ("whatsapp-qr-code-generator", "sms-qr-code-generator", "vcard-qr-code-generator"), {
        "en": _c(
            "Phone Number QR Code Generator – Tap to Call | Qrumy",
            "Make a QR code that starts a phone call to your number. Ideal for signs, "
            "vehicles and flyers. Free, no registration, PNG and SVG download.",
            "Phone Number QR Code Generator",
            "People scan the code and their phone offers to call your number — no typing, "
            "no wrong digits.",
            ["Enter the number with the country code, e.g. +994 50 123 45 67.",
             "Check the preview and choose a design that matches your brand.",
             "Download the code and add a short call to action like “Scan to call”."],
            ["Delivery vans and taxis", "“For rent” and “For sale” signs",
             "Emergency and service contacts", "Flyers for local services"],
            "A plumber puts a phone QR code on his van: drivers stuck in traffic save the "
            "number by scanning instead of trying to read it.",
            [("Does it call automatically?", "No. The phone shows the number and the person "
              "chooses to call."),
             ("Should I include the country code?", "Yes, it makes the code work for "
              "visitors and roaming phones."),
             ("Can people save my details instead?", "Use the vCard QR code or a Qrumy "
              "Card — they save your name, phone and email as a contact.")],
            "Phone QR"),
        "az": _c(
            "Telefon Nömrəsi QR Kod Generatoru – Bir Toxunuşla Zəng | Qrumy",
            "Nömrənizə zəng edən QR kod yaradın. Lövhələr, avtomobillər və bukletlər üçün "
            "idealdır. Pulsuz, qeydiyyatsız, PNG və SVG yükləmə.",
            "Telefon Nömrəsi QR Kod Generatoru",
            "İnsanlar kodu skan edir və telefon nömrənizə zəng etməyi təklif edir — yazmaq "
            "və səhv rəqəm yoxdur.",
            ["Nömrəni ölkə kodu ilə daxil edin, məs. +994 50 123 45 67.",
             "Önizləməni yoxlayın və brendinizə uyğun dizayn seçin.",
             "Kodu yükləyin və “Zəng üçün skan et” kimi qısa çağırış əlavə edin."],
            ["Çatdırılma maşınları və taksilər", "“Kirayə” və “Satılır” lövhələri",
             "Təcili və servis əlaqələri", "Yerli xidmətlər üçün bukletlər"],
            "Santexnik maşınına telefon QR kodu qoyur: tıxacdakı sürücülər nömrəni oxumağa "
            "çalışmaq əvəzinə skan edib saxlayır.",
            [("Avtomatik zəng edir?", "Xeyr. Telefon nömrəni göstərir və insan zəng etməyi "
              "özü seçir."),
             ("Ölkə kodunu yazmalıyam?", "Bəli, bu, kodun xaricdən gələnlər və rouminqdə "
              "olanlar üçün də işləməsini təmin edir."),
             ("İnsanlar məlumatlarımı yadda saxlaya bilər?", "vCard QR koddan və ya Qrumy "
              "Card-dan istifadə edin — adınızı, telefonunuzu və e-poçtunuzu kontakt kimi "
              "saxlayır.")],
            "Telefon QR"),
    }),
    Tool("whatsapp-qr-code-generator", "whatsapp", "message",
         ("phone-qr-code-generator", "url-qr-code-generator", "sms-qr-code-generator"), {
        "en": _c(
            "WhatsApp QR Code Generator – Start a Chat Instantly | Qrumy",
            "Create a WhatsApp QR code that opens a chat with your number and an optional "
            "pre-filled message. Free, no signup, download PNG or SVG.",
            "WhatsApp QR Code Generator",
            "Customers scan and land in a WhatsApp chat with you — the message can already "
            "say what they want, e.g. “I'd like to order”.",
            ["Enter your WhatsApp number with the country code.",
             "Optionally write the first message customers will send you.",
             "Download the code and put it on menus, packaging or your shop door."],
            ["Orders and reservations", "Customer support", "Price questions in a shop",
             "After-sales service"],
            "A flower shop prints a WhatsApp QR code with the message “I'd like to order a "
            "bouquet” on its business cards and bags.",
            [("Does it work with WhatsApp Business?", "Yes, it works with both WhatsApp "
              "and WhatsApp Business numbers."),
             ("Will people see my number?", "Yes — the chat opens with your number, as "
              "with any WhatsApp contact."),
             ("Can the pre-filled message be changed later?", "Not in a static code. A "
              "dynamic QR code lets you edit the message or number after printing.")],
            "WhatsApp QR"),
        "az": _c(
            "WhatsApp QR Kod Generatoru – Dərhal Söhbətə Başlayın | Qrumy",
            "Nömrənizlə və istəyə görə hazır mesajla WhatsApp söhbəti açan QR kod yaradın. "
            "Pulsuz, qeydiyyatsız, PNG və ya SVG yükləyin.",
            "WhatsApp QR Kod Generatoru",
            "Müştərilər skan edir və sizinlə WhatsApp söhbətinə düşür — mesajda artıq "
            "istədikləri yazıla bilər, məs. “Sifariş vermək istəyirəm”.",
            ["WhatsApp nömrənizi ölkə kodu ilə daxil edin.",
             "İstəsəniz müştərilərin sizə göndərəcəyi ilk mesajı yazın.",
             "Kodu yükləyin və menyulara, qablaşdırmaya və ya mağaza qapısına qoyun."],
            ["Sifariş və rezervasiyalar", "Müştəri dəstəyi", "Mağazada qiymət sualları",
             "Satışdan sonrakı xidmət"],
            "Gül mağazası vizit kartlarına və paketlərinə “Buket sifariş etmək istəyirəm” "
            "mesajlı WhatsApp QR kodu çap edir.",
            [("WhatsApp Business ilə işləyir?", "Bəli, həm WhatsApp, həm də WhatsApp "
              "Business nömrələri ilə işləyir."),
             ("İnsanlar nömrəmi görəcək?", "Bəli — söhbət istənilən WhatsApp kontaktında "
              "olduğu kimi nömrənizlə açılır."),
             ("Hazır mesajı sonra dəyişə bilərəm?", "Statik kodda yox. Dinamik QR kod "
              "çapdan sonra mesajı və ya nömrəni dəyişməyə imkan verir.")],
            "WhatsApp QR"),
    }),
    Tool("sms-qr-code-generator", "sms", "sms",
         ("whatsapp-qr-code-generator", "phone-qr-code-generator", "email-qr-code-generator"), {
        "en": _c(
            "SMS QR Code Generator – Pre-written Text Message | Qrumy",
            "Make a QR code that opens a text message to your number with the text already "
            "written. Great for opt-ins and quick replies. Free PNG/SVG.",
            "SMS QR Code Generator",
            "The code opens the messaging app with your number and a ready message — "
            "useful when people may not have WhatsApp or mobile data.",
            ["Enter the phone number that receives the messages.",
             "Write the message, e.g. a keyword like “INFO” or “BOOK 2 PEOPLE”.",
             "Download the code and test it before printing."],
            ["Keyword campaigns and opt-ins", "Quick bookings", "Votes and contests",
             "Service requests in areas with weak internet"],
            "A car service puts an SMS QR code on its windscreen stickers: “REMIND ME” "
            "books the next oil change reminder.",
            [("Does sending cost money?", "The sender pays their normal SMS rate; the QR "
              "code itself is free."),
             ("Is the SMS sent automatically?", "No, the person sees the message and taps "
              "Send."),
             ("Can I see how many people scanned?", "Static codes can't be counted. A "
              "dynamic QR code in Qrumy shows every scan by day, device and country.")],
            "SMS QR"),
        "az": _c(
            "SMS QR Kod Generatoru – Hazır Mətn Mesajı | Qrumy",
            "Mətni əvvəlcədən yazılmış SMS mesajını nömrənizə açan QR kod yaradın. Abunəlik "
            "və sürətli cavablar üçün əladır. Pulsuz PNG/SVG.",
            "SMS QR Kod Generatoru",
            "Kod mesaj tətbiqini nömrəniz və hazır mətnlə açır — WhatsApp-ı və ya mobil "
            "interneti olmayanlar üçün faydalıdır.",
            ["Mesajları alacaq telefon nömrəsini daxil edin.",
             "Mesajı yazın, məs. “INFO” və ya “2 NƏFƏR REZERV” kimi açar söz.",
             "Kodu yükləyin və çapdan əvvəl yoxlayın."],
            ["Açar sözlü kampaniyalar və abunəlik", "Sürətli rezervasiya",
             "Səsvermə və müsabiqələr", "İnterneti zəif yerlərdə servis sorğuları"],
            "Avtoservis şüşə stikerlərinə SMS QR kodu qoyur: “XATIRLAT” mesajı növbəti yağ "
            "dəyişmə xatırlatmasını sifariş edir.",
            [("Göndərmək pullu olur?", "Göndərən adi SMS tarifini ödəyir; QR kodun özü "
              "pulsuzdur."),
             ("SMS avtomatik göndərilir?", "Xeyr, insan mesajı görür və Göndər düyməsini "
              "basır."),
             ("Neçə nəfərin skan etdiyini görə bilərəm?", "Statik kodları saymaq olmur. "
              "Qrumy-də dinamik QR kod hər skanı gün, cihaz və ölkə üzrə göstərir.")],
            "SMS QR"),
    }),
    Tool("vcard-qr-code-generator", "vcard", "user",
         ("phone-qr-code-generator", "email-qr-code-generator", "url-qr-code-generator"), {
        "en": _c(
            "vCard QR Code Generator – Save Contact Details | Qrumy",
            "Create a vCard QR code for your business card. One scan saves your name, "
            "phone, email, company and website to the phone's contacts. Free.",
            "vCard QR Code Generator",
            "A vCard QR code holds a complete contact card. People scan it and tap “Save” — "
            "no more typing names and numbers from paper cards.",
            ["Fill in your name, company, job title, phone, email and website.",
             "Keep the details short: fewer characters make a cleaner, smaller code.",
             "Download SVG and give it to your printer with your business card design."],
            ["Printed business cards", "Conference badges and booths",
             "Email signatures and CVs", "Reception desks and door signs"],
            "A sales manager prints a vCard QR code on the back of her business card; after "
            "a fair, contacts are saved in seconds instead of piling up on the desk.",
            [("What is a vCard?", "A standard contact file format that iPhone, Android and "
              "Outlook can save as a contact."),
             ("Why is my vCard code so dense?", "It holds all your details. Leave out "
              "optional fields or use a Qrumy Card: the QR stays small and the page can hold "
              "photos, social links and more."),
             ("Can I update my details later?", "A static vCard can't change. A Qrumy "
              "Card (digital business card) can be edited any time without reprinting.")],
            "vCard / contact QR"),
        "az": _c(
            "vCard QR Kod Generatoru – Kontakt Məlumatlarını Saxlayın | Qrumy",
            "Vizit kartınız üçün vCard QR kod yaradın. Bir skanla adınız, telefonunuz, "
            "e-poçtunuz, şirkətiniz və saytınız kontaktlara yazılır. Pulsuz.",
            "vCard QR Kod Generatoru",
            "vCard QR kod tam kontakt kartını saxlayır. İnsanlar skan edir və “Saxla”ya "
            "basır — kağız kartlardan ad və nömrə yazmağa ehtiyac qalmır.",
            ["Adınızı, şirkətinizi, vəzifənizi, telefonunuzu, e-poçtunuzu və saytınızı "
             "doldurun.", "Məlumatları qısa saxlayın: az simvol daha təmiz, kiçik kod "
             "yaradır.", "SVG yükləyin və vizit kartı dizaynı ilə birlikdə çapçıya verin."],
            ["Çap olunmuş vizit kartları", "Konfrans bəcləri və stendlər",
             "E-poçt imzaları və CV-lər", "Qəbul masaları və qapı lövhələri"],
            "Satış meneceri vizit kartının arxasına vCard QR kod çap edir; sərgidən sonra "
            "kontaktlar masada yığılmaq əvəzinə saniyələr içində saxlanılır.",
            [("vCard nədir?", "iPhone, Android və Outlook-un kontakt kimi saxlaya bildiyi "
              "standart kontakt fayl formatıdır."),
             ("vCard kodum niyə bu qədər sıxdır?", "Bütün məlumatlarınızı saxlayır. Könüllü "
              "sahələri buraxın və ya Qrumy Card-dan istifadə edin: QR kiçik qalır, səhifədə "
              "isə foto, sosial linklər və s. ola bilər."),
             ("Məlumatlarımı sonra yeniləyə bilərəm?", "Statik vCard dəyişmir. Qrumy Card "
              "(rəqəmsal vizit kartı) yenidən çap etmədən istənilən vaxt redaktə olunur.")],
            "vCard / kontakt QR"),
    }),
    Tool("location-qr-code-generator", "location", "pin",
         ("url-qr-code-generator", "wifi-qr-code-generator", "vcard-qr-code-generator"), {
        "en": _c(
            "Location QR Code Generator – Open Google Maps | Qrumy",
            "Create a QR code that opens your location on the map with directions. Enter "
            "the coordinates, style the code and download PNG or SVG free.",
            "Location QR Code Generator",
            "The code opens a map pin at your exact location, so visitors get directions "
            "with one scan.",
            ["Find your place in Google Maps, long-press the pin and copy the coordinates.",
             "Paste the latitude and longitude, and optionally a place name.",
             "Download the code for invitations, flyers or entrance signs."],
            ["Event and wedding invitations", "Hard-to-find entrances and warehouses",
             "Hotel and apartment directions", "Delivery and pickup points"],
            "A wedding invitation includes a location QR code that opens the restaurant on "
            "the map — guests don't have to search for it.",
            [("How do I find my coordinates?", "In Google Maps, press and hold on the spot; "
              "the coordinates appear at the top or in the search bar."),
             ("Which map app opens?", "Google Maps on most phones; iPhones may ask which "
              "map app to use."),
             ("Can I add the address and phone too?", "Use a Qrumy Card for a full contact "
              "page with address, map, phone and opening hours.")],
            "Location QR"),
        "az": _c(
            "Məkan QR Kod Generatoru – Google Maps-də Açın | Qrumy",
            "Məkanınızı xəritədə yol tarifi ilə açan QR kod yaradın. Koordinatları daxil "
            "edin, dizayn seçin və PNG və ya SVG-ni pulsuz yükləyin.",
            "Məkan QR Kod Generatoru",
            "Kod dəqiq məkanınızda xəritə nişanı açır — ziyarətçilər bir skanla yol "
            "tarifini alır.",
            ["Google Maps-də yerinizi tapın, nişana uzun basın və koordinatları kopyalayın.",
             "En və uzunluq dairəsini, istəsəniz məkanın adını yapışdırın.",
             "Kodu dəvətnamələr, bukletlər və ya giriş lövhələri üçün yükləyin."],
            ["Tədbir və toy dəvətnamələri", "Çətin tapılan girişlər və anbarlar",
             "Otel və mənzil ünvanları", "Çatdırılma və götürmə nöqtələri"],
            "Toy dəvətnaməsində restoranı xəritədə açan məkan QR kodu var — qonaqlar onu "
            "axtarmalı olmur.",
            [("Koordinatlarımı necə tapım?", "Google Maps-də yerə basıb saxlayın; "
              "koordinatlar yuxarıda və ya axtarış sətrində görünür."),
             ("Hansı xəritə tətbiqi açılır?", "Əksər telefonlarda Google Maps; iPhone hansı "
              "xəritə tətbiqindən istifadə edəcəyini soruşa bilər."),
             ("Ünvan və telefon da əlavə edə bilərəm?", "Ünvan, xəritə, telefon və iş "
              "saatları olan tam əlaqə səhifəsi üçün Qrumy Card-dan istifadə edin.")],
            "Məkan QR"),
    }),
    Tool("text-qr-code-generator", "text", "text",
         ("url-qr-code-generator", "wifi-qr-code-generator", "qr-code-generator"), {
        "en": _c(
            "Text QR Code Generator – Plain Text QR | Qrumy",
            "Turn a short text into a QR code that shows it on any phone — no internet "
            "needed to read it. Free, no signup, PNG and SVG download.",
            "Text QR Code Generator",
            "The text is stored inside the code itself, so it can be read even without an "
            "internet connection.",
            ["Type or paste your text — up to about 300 characters keeps the code easy to "
             "scan.", "Check the preview; long texts create denser codes.",
             "Download and print. Test it with two phones before a large print run."],
            ["Serial numbers and inventory labels", "Short instructions on equipment",
             "Treasure hunts and games", "Messages on gifts and invitations"],
            "A warehouse labels shelves with text QR codes containing the location code, "
            "so workers can scan them offline.",
            [("How long can the text be?", "Technically over a thousand characters, but "
              "short texts make small codes that scan easily."),
             ("Does reading the text need internet?", "No, the phone decodes it directly "
              "from the image."),
             ("Can I format the text?", "No, it is plain text. For a styled page with "
              "images and links, use a dynamic QR code with a landing page.")],
            "Text QR"),
        "az": _c(
            "Mətn QR Kod Generatoru – Sadə Mətn QR | Qrumy",
            "Qısa mətni istənilən telefonda göstərən QR koda çevirin — oxumaq üçün internet "
            "lazım deyil. Pulsuz, qeydiyyatsız, PNG və SVG yükləmə.",
            "Mətn QR Kod Generatoru",
            "Mətn kodun özündə saxlanılır, ona görə internet olmadan da oxuna bilər.",
            ["Mətninizi yazın və ya yapışdırın — təxminən 300 simvola qədər kodu asan "
             "skan edilən saxlayır.", "Önizləməni yoxlayın; uzun mətnlər daha sıx kod "
             "yaradır.", "Yükləyin və çap edin. Böyük tirajdan əvvəl iki telefonla yoxlayın."],
            ["Seriya nömrələri və anbar etiketləri", "Avadanlıq üzərində qısa təlimatlar",
             "Xəzinə axtarışı və oyunlar", "Hədiyyə və dəvətnamələrdə mesajlar"],
            "Anbar rəfləri yer kodu olan mətn QR kodları ilə etiketlənir — işçilər onları "
            "internetsiz skan edir.",
            [("Mətn nə qədər uzun ola bilər?", "Texniki olaraq min simvoldan çox, amma "
              "qısa mətnlər asan skan edilən kiçik kod yaradır."),
             ("Mətni oxumaq üçün internet lazımdır?", "Xeyr, telefon onu birbaşa şəkildən "
              "oxuyur."),
             ("Mətni formatlaya bilərəm?", "Xeyr, bu sadə mətndir. Şəkil və linkləri olan "
              "səhifə üçün açılış səhifəli dinamik QR koddan istifadə edin.")],
            "Mətn QR"),
    }),
]

TOOLS_BY_SLUG = {t.slug: t for t in TOOLS}


def content(tool: Tool, language: str) -> dict:
    return tool.content.get(language) or tool.content["en"]
