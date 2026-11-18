# Example answers

The case's questions asked end-to-end over HTTP against the Docker stack
(`POST /api/chat`, one session, 2026-11-18). Answers are verbatim;
"Agent" shows the tool calls streamed as `tool_start` events.

## 1. Vad erbjuder ni för typer av AI-tjänster?

*Agent:* search_website('AI-tjänster') · *first token* 1.9 s · *total* 3.6 s

> Compileit erbjuder AI-tjänster som hjälper företag att koppla AI direkt till sina processer för att spara tid och effektivisera arbetet. De bygger AI-agenter som kan automatisera repetitiva uppgifter, optimera processer och ge insikter i realtid. Exempel är AI-agenter som hanterar kundserviceärenden dygnet runt, vilket minskat ärenden med 61 % för SkiStar. De hjälper också till med AI-assistenter för ekonomi, inköp, försäljning och bokning. Tjänsterna inkluderar rådgivning för att hitta rätt AI-initiativ och säkerställa dataskydd och kvalitet. Boka gärna en kostnadsfri konsultation för att kartlägga era behov.
>
> Mer om AI-tjänsterna finns på [AI-agenter & automation för din organisation](https://compileit.com/tjanster/ai).

*Source cards:* [AI-agenter & automation för din organisation](https://compileit.com/tjanster/ai)

## 2. Vilka branscher jobbar ni med?

*Agent:* search_website('branscher kunder'), get_page('/uppdrag') · *first token* 3.2 s · *total* 4.6 s

> Compileit jobbar med flera branscher, bland annat:
>
> - Fastigheter (t.ex. Balder med digital bostadskö)
> - Betalningstjänster (Swish)
> - Turism och sport (SkiStar, inklusive AI-agent för kundservice)
> - Detaljhandel och e-handel (Jula, Equestrian Stockholm)
> - Hälsa och välmående (Hästens Restore)
> - Ideella organisationer (Barncancerfonden)
> - Digitalisering och plattformar (Trifam, CIBoost)
> - Bokningstjänster (Bokadirekt)
>
> Det är en sammanställning baserad på deras uppdrag, se mer på [Ett urval av våra uppdrag](https://compileit.com/uppdrag).

*Source cards:* [Ett urval av våra uppdrag](https://compileit.com/uppdrag)

## 3. Hur kontaktar man er, och var sitter ni?

*Agent:* search_website('kontakt adress') · *first token* 1.7 s · *total* 2.8 s

> Du kan kontakta Compileit genom att fylla i kontaktformuläret på deras webbplats eller mejla direkt till hello@compileit.com. De har kontor i Stockholm, Kalmar och Skövde:
>
> - Stockholm: Olof Palmes Gata 13, 111 37 Stockholm  
> - Kalmar: Larmgatan 14, 392 32 Kalmar  
> - Skövde: Kanikegränd 3B, 549 34 Skövde  
>
> Mer information och kontaktuppgifter finns på sidan [Kontakta oss](https://compileit.com/kontakt).

*Source cards:* [Kontakta oss](https://compileit.com/kontakt)

## 4. Har ni beskrivit hur ni jobbar med säkerhet/sekretess?

*Agent:* search_website('säkerhet sekretess') · *first token* 2.1 s · *total* 3.9 s

> Ja, Compileit beskriver sitt arbete med säkerhet och sekretess i sin integritetspolicy. De behandlar personuppgifter för att säkerställa webbplatsens funktion och skydda mot obehörig åtkomst och säkerhetshot. De använder tekniska och organisatoriska åtgärder för att skydda personuppgifter mot förlust, ändring och otillåten användning, och begränsar åtkomsten till behöriga personer. Personuppgifter sparas endast så länge det behövs och raderas säkert när de inte längre behövs.
>
> De betonar också vikten av mänskligt omdöme och ansvar för att säkerställa säkerhet i produktutveckling, särskilt i AI-sammanhang.
>
> Mer detaljer finns i deras [Integritetspolicy](https://compileit.com/privacy-policy) och i artikeln [När alla kan koda – hur vinner du då?](https://compileit.com/kunskap/naer-alla-kan-koda-hur-vinner-du-da).

*Source cards:* [Integritetspolicy](https://compileit.com/privacy-policy), [När alla kan koda – hur vinner du då?](https://compileit.com/kunskap/naer-alla-kan-koda-hur-vinner-du-da)

## 5. Sammanfatta sidan 'Om oss' i tre punkter och länka källan.

*Agent:* search_website('Om oss') · *first token* 1.8 s · *total* 3.4 s

> Här är en sammanfattning av sidan "Om oss" i tre punkter:
>
> - Compileit skiljer sig genom att satsa på partnerskap med kunder där lösningar ska göra verklig nytta, med fokus på användare, affär och samhälle. De värdesätter också en inkluderande och rolig arbetskultur.
> - Företaget grundades 2022 av Isak och Jonathan, som har lång erfarenhet från techbranschen och ville skapa ett techbolag där värde går före fakturerbara timmar.
> - Compileit attraherar topptalanger genom att erbjuda en miljö med snabb personlig utveckling, ansvar och arbete med teknik i framkant, med en kultur av lärande och innovation.
>
> Källa: [Om oss](https://compileit.com/om-oss)

*Source cards:* [Om Compileit](https://compileit.com/om-oss)

## 6. Berätta mer om den andra punkten

*Agent:* search_website('grundare historia Compileit') · *first token* 2.7 s · *total* 4.7 s

> Grundarna Isak och Jonathan startade Compileit 2022 efter att ha samlat erfarenhet från techbranschen i över ett decennium, där de bland annat blivit stämda av Snapchat, hyllade av Apple och Google, och byggt några av världens mest nedladdade appar. De var trötta på branschens fokus på timmar, leverabler och prestige, där affären och användaren ofta tappades bort. Med en gemensam övertygelse om att driva ett techbolag där både kunder, medarbetare och användare vinner på slutresultatet, grundades Compileit. Företaget prioriterar värde framför fakturerbara timmar och ger plats för bra idéer.
>
> Mer finns att läsa på [Om oss](https://compileit.com/om-oss) och [Karriär](https://compileit.com/karriar).

*Source cards:* [Karriär](https://compileit.com/karriar), [Om Compileit](https://compileit.com/om-oss)

## 7. Vad kostar en Tesla?

*Agent:* search_website('Tesla pris') · *first token* 2.2 s · *total* 2.7 s

> Det hittar jag inte på compileit.com. Jag kan hjälpa dig med frågor om Compileit, deras tjänster, uppdrag eller liknande. Vill du veta mer om Compileits arbete med AI eller digitala lösningar? Se [Compileit](https://compileit.com).

*Source cards:* - (none)
