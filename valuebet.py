import streamlit as st
import math
import requests
import pandas as pd
import plotly.express as px

if 'kupon' not in st.session_state:
    st.session_state.kupon = []

if 'pokaz_wyniki' not in st.session_state:
    st.session_state.pokaz_wyniki = False

def dodaj_do_kuponu(mecz_str, typ_str, kurs_val):
    st.session_state.kupon.append({"mecz": mecz_str, "typ": typ_str, "kurs": kurs_val})

KLUCZ_API = "797ea88129cf462dbcb4ea28dfad4042"
NAGLOWKI = {"X-Auth-Token": KLUCZ_API}

LIGI = {
    "Premier League (Anglia)": "PL",
    "La Liga (Hiszpania)": "PD",
    "Bundesliga (Niemcy)": "BL1",
    "Serie A (Włochy)": "SA",
    "Ligue 1 (Francja)": "FL1"
}

@st.cache_data(ttl=43200)
def pobierz_dane_ligi(kod_ligi):
    url = f"https://api.football-data.org/v4/competitions/{kod_ligi}/matches"
    response = requests.get(url, headers=NAGLOWKI)
    if response.status_code != 200:
        return []
    return response.json().get('matches', [])

def pobierz_ostatnie_mecze_szczegoly(nazwa_druzyny, wszystkie_mecze):
    mecze_druzyny = [m for m in wszystkie_mecze if m['status'] == 'FINISHED' and (m['homeTeam']['name'] == nazwa_druzyny or m['awayTeam']['name'] == nazwa_druzyny)]
    mecze_druzyny.sort(key=lambda x: x['utcDate'], reverse=True)
    ostatnie_10 = mecze_druzyny[:10]
    
    dane_wykres = []
    strzelone = stracone = 0
    
    for m in ostatnie_10:
        gospodarz = m['homeTeam']['name']
        data_meczu = m['utcDate'][:10]
        score = m.get('score', {}).get('fullTime', {})
        g_dom = score.get('home', 0) if score.get('home') is not None else 0
        g_wyj = score.get('away', 0) if score.get('away') is not None else 0
        
        if gospodarz == nazwa_druzyny:
            strz = g_dom
            strac = g_wyj
            przeciwnik = m['awayTeam']['name']
        else:
            strz = g_wyj
            strac = g_dom
            przeciwnik = m['homeTeam']['name']
            
        strzelone += strz
        stracone += strac
        dane_wykres.append({"Data": data_meczu, "Przeciwnik": przeciwnik, "Strzelone": strz, "Stracone": strac})
        
    rozegrane = len(ostatnie_10)
    srednia_strz = strzelone / rozegrane if rozegrane > 0 else 1.3
    srednia_strac = stracone / rozegrane if rozegrane > 0 else 1.1
    
    return srednia_strz, srednia_strac, rozegrane, dane_wykres

def pobierz_h2h(gospodarz, gosc, wszystkie_mecze):
    h2h = [m for m in wszystkie_mecze if m['status'] == 'FINISHED' and 
           ((m['homeTeam']['name'] == gospodarz and m['awayTeam']['name'] == gosc) or 
            (m['homeTeam']['name'] == gosc and m['awayTeam']['name'] == gospodarz))]
    h2h.sort(key=lambda x: x['utcDate'], reverse=True)
    return h2h[:5]

def prawdopodobienstwo_poissona(srednia_goli, liczba_goli):
    return ((srednia_goli ** liczba_goli) * math.exp(-srednia_goli)) / math.factorial(liczba_goli)

# --- INTERFEJS APLIKACJI ---

st.title("🚀 Pro System Analityczny z Skanerem i Kuponem")

if KLUCZ_API == "TUTAJ_WKLEJ_SWOJ_TOKEN":
    st.error("Wklej swój token API w kodzie pliku!")
else:
    tryb = st.radio("Wybierz tryb pracy:", ["🔍 Analiza pojedynczego meczu", "⚡ Skaner całej kolejki", "📡 Radar (Watchlist)"], horizontal=True)
    st.divider()
    
    wszystkie_mecze = []
    
    if tryb == "📡 Radar (Watchlist)":
        with st.spinner("Pobieranie i łączenie danych z Top 5 Lig Europy..."):
            for kod in LIGI.values():
                wszystkie_mecze.extend(pobierz_dane_ligi(kod))
    else:
        wybrana_liga = st.selectbox("Wybierz ligę:", list(LIGI.keys()))
        kod_ligi = LIGI[wybrana_liga]
        with st.spinner("Pobieranie danych..."):
            wszystkie_mecze = pobierz_dane_ligi(kod_ligi)
            
    if not wszystkie_mecze:
        st.warning("Brak danych z API.")
    else:
        nadchodzace = [m for m in wszystkie_mecze if m['status'] in ['SCHEDULED', 'TIMED', 'LIVE', 'IN_PLAY']]
        
        # --- NOWY TRYB: RADAR ---
        if tryb == "📡 Radar (Watchlist)":
            st.subheader(f"📡 Globalny Radar Drużyn – Top 5 Lig")
            st.write("Wybierz drużyny z dowolnej z pięciu najlepszych lig, które chcesz śledzić. Radar wychwyci anomalie, gdy bukmacherzy zaniżają kursy na faworytów przez tzw. 'owczy pęd' graczy.")
            
            druzyny_w_lidze = set()
            for m in wszystkie_mecze:
                druzyny_w_lidze.add(m['homeTeam']['name'])
                druzyny_w_lidze.add(m['awayTeam']['name'])
                
            obserwowane = st.multiselect("Wybierz zespoły do radaru (możesz wyszukiwać wpisując nazwę):", sorted(list(druzyny_w_lidze)))
            
            if obserwowane:
                mecze_radaru = [m for m in nadchodzace if m['homeTeam']['name'] in obserwowane or m['awayTeam']['name'] in obserwowane]
                
                if not mecze_radaru:
                    st.info("Brak nadchodzących meczów dla wybranych drużyn w systemie.")
                else:
                    for m in mecze_radaru:
                        h_name = m['homeTeam']['name']
                        a_name = m['awayTeam']['name']
                        
                        strz_g, strac_g, il_g, _ = pobierz_ostatnie_mecze_szczegoly(h_name, wszystkie_mecze)
                        strz_w, strac_w, il_w, _ = pobierz_ostatnie_mecze_szczegoly(a_name, wszystkie_mecze)
                        
                        exp_gosp = (strz_g + strac_w) / 2
                        exp_gosc = (strz_w + strac_g) / 2
                        
                        p_1 = p_x = p_2 = 0
                        for gd in range(6):
                            for gw in range(6):
                                p = prawdopodobienstwo_poissona(exp_gosp, gd) * prawdopodobienstwo_poissona(exp_gosc, gw)
                                if gd > gw: p_1 += p
                                elif gd == gw: p_x += p
                                else: p_2 += p
                                
                        suma = p_1 + p_x + p_2
                        s1 = (p_1 / suma) * 100 if suma > 0 else 0
                        sx = (p_x / suma) * 100 if suma > 0 else 0
                        s2 = (p_2 / suma) * 100 if suma > 0 else 0
                        
                        fair_1 = 100/s1 if s1 > 0 else 0
                        fair_x = 100/sx if sx > 0 else 0
                        fair_2 = 100/s2 if s2 > 0 else 0
                        
                        sledzona = h_name if h_name in obserwowane else a_name
                        przeciwnik = a_name if h_name in obserwowane else h_name
                        
                        with st.expander(f"👁️ Mecz: {h_name} vs {a_name} ({m['utcDate'][:10]})", expanded=True):
                            st.write(f"**Śledzisz:** `{sledzona}`")
                            
                            c_kurs1, c_kurs2, c_kurs3 = st.columns(3)
                            k_1 = c_kurs1.number_input(f"Bukmacher: 1 ({h_name})", value=2.00, step=0.05, key=f"r1_{m['id']}")
                            k_x = c_kurs2.number_input(f"Bukmacher: X", value=3.20, step=0.05, key=f"rx_{m['id']}")
                            k_2 = c_kurs3.number_input(f"Bukmacher: 2 ({a_name})", value=3.50, step=0.05, key=f"r2_{m['id']}")
                            
                            ev_1 = (k_1 * (s1/100)) - 1
                            ev_x = (k_x * (sx/100)) - 1
                            ev_2 = (k_2 * (s2/100)) - 1
                            
                            st.write("---")
                            if h_name == sledzona:
                                szansa_sledzonej = s1
                                fair_sledzonej = fair_1
                                ev_sledzonej = ev_1
                                k_sledzonej = k_1
                                k_przeciwnika = k_2
                                nazwa_zakladu_przeciwko = f"X2 ({przeciwnik} nie przegra)"
                            else:
                                szansa_sledzonej = s2
                                fair_sledzonej = fair_2
                                ev_sledzonej = ev_2
                                k_sledzonej = k_2
                                k_przeciwnika = k_1
                                nazwa_zakladu_przeciwko = f"1X ({przeciwnik} nie przegra)"

                            if ev_sledzonej > 0:
                                st.success(f"🟢 **Czyste Value!** Rynek niedocenia `{sledzona}`. Bukmacher płaci {k_sledzonej}, a uczciwy kurs z matematyki to {fair_sledzonej:.2f}.")
                            elif ev_sledzonej < -0.15 and k_sledzonej < 1.60:
                                st.error(f"🔴 **Przegrzany Rynek (Overvalued)!** Tłum masowo obstawia `{sledzona}` zbijając kurs do {k_sledzonej}. Model pokazuje, że to nieopłacalne (Fair: {fair_sledzonej:.2f}).")
                                st.warning(f"💡 **Zagranie Contrarian:** Rozważ typ **{nazwa_zakladu_przeciwko}** lub handicap w stronę drużyny `{przeciwnik}`. Bukmacher przepłaca za niespodziankę!")
                            else:
                                st.info(f"⚪ **Rynek stabilny.** Kursy bukmachera ({k_sledzonej}) pokrywają się z grubsza z modelem ({fair_sledzonej:.2f}). Brak anomalii.")

        # --- TRYB: SKANER CAŁEJ KOLEJKI ---
        elif tryb == "⚡ Skaner całej kolejki":
            st.subheader(f"⚡ Skaner nadchodzących meczów: {wybrana_liga}")
            uwzglednij_dom_skaner = st.checkbox("🏠 Uwzględnij atut własnego boiska w skanerze", value=False)
            
            if st.button("Uruchom skaner dla całej ligi"):
                with st.spinner("Przeliczanie modelu Poissona dla wszystkich spotkań..."):
                    wyniki_skanera = []
                    for m in nadchodzace:
                        h_name = m['homeTeam']['name']
                        a_name = m['awayTeam']['name']
                        
                        strz_g, strac_g, il_g, _ = pobierz_ostatnie_mecze_szczegoly(h_name, wszystkie_mecze)
                        strz_w, strac_w, il_w, _ = pobierz_ostatnie_mecze_szczegoly(a_name, wszystkie_mecze)
                        
                        exp_gosp = (strz_g + strac_w) / 2
                        exp_gosc = (strz_w + strac_g) / 2
                        
                        if uwzglednij_dom_skaner:
                            exp_gosp *= 1.10
                            exp_gosc *= 0.95
                            
                        p_1 = p_x = p_2 = p_btts = p_over = 0
                        for gd in range(6):
                            for gw in range(6):
                                p = prawdopodobienstwo_poissona(exp_gosp, gd) * prawdopodobienstwo_poissona(exp_gosc, gw)
                                if gd > gw: p_1 += p
                                elif gd == gw: p_x += p
                                else: p_2 += p
                                if gd >= 1 and gw >= 1: p_btts += p
                                if (gd + gw) >= 3: p_over += p
                        
                        suma = p_1 + p_x + p_2
                        if suma > 0:
                            s1 = (p_1 / suma) * 100
                            sx = (p_x / suma) * 100
                            s2 = (p_2 / suma) * 100
                            sb = (p_btts / suma) * 100
                            so = (p_over / suma) * 100
                            
                            wyniki_skanera.append({
                                "Data": m['utcDate'][:10],
                                "Mecz": f"{h_name} vs {a_name}",
                                "Model 1 (%)": f"{s1:.1f}%",
                                "Fair 1": f"{100/s1:.2f}" if s1>0 else "-",
                                "Model X (%)": f"{sx:.1f}%",
                                "Fair X": f"{100/sx:.2f}" if sx>0 else "-",
                                "Model 2 (%)": f"{s2:.1f}%",
                                "Fair 2": f"{100/s2:.2f}" if s2>0 else "-",
                                "BTTS (%)": f"{sb:.1f}%",
                                "Over 2.5 (%)": f"{so:.1f}%"
                            })
                    
                    if wyniki_skanera:
                        df_skaner = pd.DataFrame(wyniki_skanera)
                        st.dataframe(df_skaner, use_container_width=True)
                        st.info("💡 Porównaj kolumny 'Fair' ze swoimi bukmacherami – jeśli kurs u buka jest wyższy niż 'Fair', masz do czynienia z Value Betem!")
                    else:
                        st.warning("Brak meczów do przetworzenia.")
                        
        # --- TRYB: POJEDYNCZY MECZ ---
        else:
            if not nadchodzace:
                st.warning("Brak nadchodzących meczów.")
            else:
                opcje = {f"{m['utcDate'][:10]} | {m['homeTeam']['name']} vs {m['awayTeam']['name']}": m for m in nadchodzace}
                
                poprzedni_mecz = st.session_state.get('wybrany_mecz_tekst', '')
                wybrany_tekst = st.selectbox("Wybierz spotkanie:", list(opcje.keys()))
                if poprzedni_mecz != wybrany_tekst:
                    st.session_state.wybrany_mecz_tekst = wybrany_tekst
                    st.session_state.pokaz_wyniki = False
                
                mecz = opcje[wybrany_tekst]
                gospodarz = mecz['homeTeam']['name']
                gosc = mecz['awayTeam']['name']
                
                st.divider()
                st.subheader(f"⚽ {gospodarz} vs {gosc}")
                
                uwzglednij_dom = st.checkbox("🏠 Uwzględnij atut własnego boiska (korekta +10% dla gospodarza)", value=False)
                
                strz_g, strac_g, il_g, hist_g = pobierz_ostatnie_mecze_szczegoly(gospodarz, wszystkie_mecze)
                strz_w, strac_w, il_w, hist_w = pobierz_ostatnie_mecze_szczegoly(gosc, wszystkie_mecze)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"**Gospodarz ({gospodarz})**\n* Ostatnie mecze: {il_g}\n* Strzela: {strz_g:.2f} | Traci: {strac_g:.2f}")
                with c2:
                    st.info(f"**Gość ({gosc})**\n* Ostatnie mecze: {il_w}\n* Strzela: {strz_w:.2f} | Traci: {strac_w:.2f}")
                
                with st.expander("🗓️ Szczegółowe wyniki ostatnich meczów (Z kim grali?)"):
                    col_hist1, col_hist2 = st.columns(2)
                    with col_hist1:
                        for h in hist_g:
                            ikona = "🟢" if h['Strzelone'] > h['Stracone'] else ("🔴" if h['Strzelone'] < h['Stracone'] else "⚪")
                            st.write(f"{ikona} `{h['Strzelone']}:{h['Stracone']}` vs {h['Przeciwnik']} ({h['Data']})")
                    with col_hist2:
                        for h in hist_w:
                            ikona = "🟢" if h['Strzelone'] > h['Stracone'] else ("🔴" if h['Strzelone'] < h['Stracone'] else "⚪")
                            st.write(f"{ikona} `{h['Strzelone']}:{h['Stracone']}` vs {h['Przeciwnik']} ({h['Data']})")

                exp_gosp = (strz_g + strac_w) / 2
                exp_gosc = (strz_w + strac_g) / 2
                
                if uwzglednij_dom:
                    exp_gosp *= 1.10
                    exp_gosc *= 0.95
                
                with st.expander("📈 Zobacz wykresy formy (Bramki w ostatnich meczach)"):
                    col_w1, col_w2 = st.columns(2)
                    with col_w1:
                        st.write(f"Forma: **{gospodarz}**")
                        if hist_g:
                            df_g = pd.DataFrame(hist_g)
                            fig_g = px.bar(df_g, x='Data', y=['Strzelone', 'Stracone'], barmode='group', title="Gospodarz")
                            st.plotly_chart(fig_g, use_container_width=True)
                    with col_w2:
                        st.write(f"Forma: **{gosc}**")
                        if hist_w:
                            df_w = pd.DataFrame(hist_w)
                            fig_w = px.bar(df_w, x='Data', y=['Strzelone', 'Stracone'], barmode='group', title="Gość")
                            st.plotly_chart(fig_w, use_container_width=True)
                
                max_gole = 6
                macierz = [[0.0]*max_gole for _ in range(max_gole)]
                p_1 = p_x = p_2 = 0
                p_btts_tak = p_over_25 = 0
                
                for gd in range(max_gole):
                    for gw in range(max_gole):
                        p = prawdopodobienstwo_poissona(exp_gosp, gd) * prawdopodobienstwo_poissona(exp_gosc, gw)
                        macierz[gd][gw] = p
                        if gd > gw: p_1 += p
                        elif gd == gw: p_x += p
                        else: p_2 += p
                        
                        if gd >= 1 and gw >= 1: p_btts_tak += p
                        if (gd + gw) >= 3: p_over_25 += p
                            
                suma = p_1 + p_x + p_2
                sz_1 = (p_1 / suma) * 100
                sz_x = (p_x / suma) * 100
                sz_2 = (p_2 / suma) * 100
                sz_btts = (p_btts_tak / suma) * 100
                sz_over25 = (p_over_25 / suma) * 100
                
                st.write("#### 🤖 Szanse 1X2 (Model Poissona):")
                m1, m2, m3 = st.columns(3)
                m1.metric(f"1 ({gospodarz})", f"{sz_1:.1f}%", f"Fair: {100/sz_1:.2f}")
                m2.metric("X (Remis)", f"{sz_x:.1f}%", f"Fair: {100/sz_x:.2f}")
                m3.metric(f"2 ({gosc})", f"{sz_2:.1f}%", f"Fair: {100/sz_2:.2f}")
                
                st.write("#### 🎯 Szanse na Rynki Dodatkowe:")
                b1, b2 = st.columns(2)
                b1.metric("BTTS (Obie strzelą)", f"{sz_btts:.1f}%", f"Fair: {100/sz_btts:.2f}")
                b2.metric("Over 2.5 gola", f"{sz_over25:.1f}%", f"Fair: {100/sz_over25:.2f}")
                
                with st.expander("📊 Zobacz macierz prawdopodobieństwa dokładnych wyników"):
                    df_macierz = pd.DataFrame(
                        [[f"{macierz[gd][gw]*100:.1f}%" for gw in range(5)] for gd in range(5)],
                        index=[f"Dom {gd}" for gd in range(5)],
                        columns=[f"Wyjazd {gw}" for gw in range(5)]
                    )
                    st.dataframe(df_macierz, use_container_width=True)

                st.divider()
                st.subheader("💰 Weryfikacja Value & Wirtualny Kupon")
                
                bankroll = st.number_input("Twój budżet (Bankroll w PLN):", min_value=10.0, value=1000.0, step=50.0)
                
                col_k1, col_k2 = st.columns(2)
                with col_k1:
                    k_1 = st.number_input(f"Kurs 1 ({gospodarz})", min_value=1.01, value=2.10, step=0.05, key="k1")
                    k_x = st.number_input("Kurs X (Remis)", min_value=1.01, value=3.40, step=0.05, key="kx")
                    k_2 = st.number_input(f"Kurs 2 ({gosc})", min_value=1.01, value=3.20, step=0.05, key="k2")
                with col_k2:
                    k_btts = st.number_input("Kurs BTTS (TAK)", min_value=1.01, value=1.85, step=0.05, key="kbtts")
                    k_over = st.number_input("Kurs Over 2.5", min_value=1.01, value=1.90, step=0.05, key="kover")
                
                if st.button("Sprawdź Opłacalność (EV) i Pokaż Wyniki"):
                    st.session_state.pokaz_wyniki = True

                if st.session_state.pokaz_wyniki:
                    zaklady_dostepne = [
                        (f"1: {gospodarz}", k_1, sz_1),
                        ("X: Remis", k_x, sz_x),
                        (f"2: {gosc}", k_2, sz_2),
                        ("BTTS: TAK", k_btts, sz_btts),
                        ("Over 2.5", k_over, sz_over25)
                    ]
                    
                    st.write("### Wyniki analizy opłacalności (EV):")
                    for nazwa, kurs, szansa in zaklady_dostepne:
                        p = szansa / 100
                        ev = (kurs * p) - 1
                        fair = 100 / szansa if szansa > 0 else 0
                        
                        kelly = max(0, ((p * kurs - 1) / (kurs - 1)) * 0.25)
                        stawka = bankroll * kelly
                        
                        col_info, col_btn = st.columns([4, 1])
                        with col_info:
                            if ev > 0:
                                st.success(f"✅ **{nazwa}** | Kurs: {kurs} | Model: {szansa:.1f}% (Fair: {fair:.2f}) -> **VALUE!** (+{ev*100:.2f}%) | Kelly: {stawka:.2f} PLN")
                            else:
                                st.error(f"❌ **{nazwa}** | Kurs: {kurs} | Model: {szansa:.1f}% (Fair: {fair:.2f}) -> Brak value ({ev*100:.2f}%)")
                        
                        with col_btn:
                            st.button(
                                "Dodaj", 
                                key=f"add_{nazwa}_{gospodarz}_{mecz['id']}",
                                on_click=dodaj_do_kuponu,
                                args=(f"{gospodarz} vs {gosc}", nazwa, kurs)
                            )
                
                st.divider()
                st.subheader("🏃 Ręczny Kalkulator Strzelca (Player Props)")
                col_strz1, col_strz2, col_strz3 = st.columns(3)
                with col_strz1:
                    druzyna_strzelca = st.radio("Zawodnik z drużyny:", [gospodarz, gosc])
                with col_strz2:
                    udzial_procent = st.number_input("Udział w golach drużyny (%)", min_value=1.0, max_value=100.0, value=25.0, step=1.0)
                with col_strz3:
                    kurs_strzelec = st.number_input("Kurs na gola", min_value=1.01, value=2.50, step=0.05, key="k_strzelec")
                
                nazwa_strzelca = st.text_input("Nazwa zawodnika (opcjonalnie do kuponu):", value="Zawodnik X")

                if st.button("Oblicz Value dla Strzelca"):
                    team_xg = exp_gosp if druzyna_strzelca == gospodarz else exp_gosc
                    player_xg = team_xg * (udzial_procent / 100)
                    
                    p_0 = prawdopodobienstwo_poissona(player_xg, 0)
                    p_strzeli = 1 - p_0
                    szansa_strzeli_proc = p_strzeli * 100
                    fair_strzelec = 1 / p_strzeli if p_strzeli > 0 else 0
                    ev_strzelec = (kurs_strzelec * p_strzeli) - 1
                    
                    kelly_strzelec = max(0, ((p_strzeli * kurs_strzelec - 1) / (kurs_strzelec - 1)) * 0.25)
                    stawka_strzelec = bankroll * kelly_strzelec
                    
                    st.write(f"**xG drużyny:** `{team_xg:.2f}` ➔ **Indywidualne xG zawodnika:** `{player_xg:.2f}`")
                    
                    c_info_strz, c_btn_strz = st.columns([4, 1])
                    with c_info_strz:
                        if ev_strzelec > 0:
                            st.success(f"✅ **Gol: {nazwa_strzelca}** | Kurs: {kurs_strzelec} | Model: {szansa_strzeli_proc:.1f}% (Fair: {fair_strzelec:.2f}) -> **VALUE!** (+{ev_strzelec*100:.2f}%) | Kelly: {stawka_strzelec:.2f} PLN")
                        else:
                            st.error(f"❌ **Gol: {nazwa_strzelca}** | Kurs: {kurs_strzelec} | Model: {szansa_strzeli_proc:.1f}% (Fair: {fair_strzelec:.2f}) -> Brak value ({ev_strzelec*100:.2f}%)")
                    
                    with c_btn_strz:
                        st.button(
                            "Dodaj", 
                            key=f"add_strzelec_{mecz['id']}_{nazwa_strzelca}",
                            on_click=dodaj_do_kuponu,
                            args=(f"{gospodarz} vs {gosc}", f"Gol: {nazwa_strzelca}", kurs_strzelec)
                        )

        st.divider()
        st.subheader("🎟️ Twój Wirtualny Kupon (Bet Slip)")
        if not st.session_state.kupon:
            st.info("Kupon jest pusty. Wybierz mecz, kliknij 'Sprawdź Opłacalność' i dodaj wybrane typy.")
        else:
            ak_kurs = 1.0
            for i, t in enumerate(st.session_state.kupon):
                st.write(f"{i+1}. **{t['mecz']}** | Typ: **{t['typ']}** | Kurs: `{t['kurs']}`")
                ak_kurs *= t['kurs']
            
            st.write(f"**Kurs łączny AKO:** `{ak_kurs:.2f}`")
            
            if st.button("Wyczyść kupon"):
                st.session_state.kupon = []
                st.rerun()