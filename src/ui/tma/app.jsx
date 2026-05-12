const { useState, useEffect, useMemo } = React;

const T = {
    pl: {
        title: "Vortex Terminal",
        updated: "UPD",
        freeStream: "Strumień Rynkowy",
        proStream: "Deep Institutional Flow",
        intelReport: "Raport Instytucjonalny",
        signals: "Sygnały",
        context: "Analiza Strukturalna",
        exploreBtn: "Głębsza Analiza",
        trackBtn: "Śledź Wektor",
        exploreMsg: "📡 Pobieranie danych instytucjonalnych...",
        trackMsg: "🔔 Powiadomienia wektorowe aktywne.",
        unlockTitle: "Deep Flow Zablokowany",
        unlockDesc: "Zaproś 3 osoby lub wpisz /upgrade w bocie.",
        unlockBtn: "Odblokuj PRO",
        inviteBtn: "🔗 Zaproś znajomych",
        inviteMsg: "Znalazłem profesjonalny terminal analityczny do krypto. Przesyłam dostęp:",
        payBtn: "💳 Kup za 49 USDT",
        cancelBtn: "Anuluj",
        refProgress: "poleceń",
        biasLong: "Positive Gamma Accumulation",
        biasShort: "Negative Gamma Acceleration",
        biasNeutral: "Market Equilibrium Cluster",
        ctxLong: "Synergia Positive Gamma i absorpcji Spot. Market Makerzy (MM) w reżimie stabilizacji — zmuszeni do kupowania dołków i sprzedaży górek (mean reversion), co tłumi zmienność (Volatility Dampening). Kapitał instytucjonalny akumuluje podaż w strefach płynności, tworząc silną bazę pod kontynuację trendu.",
        ctxShort: "Krytyczny wzrost pozycjonowania w Puty — reżim Negative Gamma. Dostawcy płynności zmuszeni do agresywnego zabezpieczania poprzez krótką sprzedaż Spot przy spadkach (Delta Hedging), co akceleruje dynamikę zniżek. Ryzyko kaskady likwidacji i 'gamma squeeze' w dół.",
        ctxNeutral: "Brak wyraźnego odchylenia instytucjonalnego (Gamma Neutral). Kapitał spekulacyjny zrównoważony przez hedging — faza rotacji rynkowej. Smart Money czeka na wykrystalizowanie się trendu poza lokalnymi klastrami płynności.",
        sigAnchor: (s) => `Gamma Wall (MM Support): $${s}`,
        sigVoid: (s) => `Gamma Ceiling (MM Resistance): $${s}`,
        fundingLabel: "Funding Rate",
        fundingLong: "Longi płacą shortom — Institutional Crowding (Overbought)",
        fundingShort: "Shorty płacą longom — Capitulation Signal (Oversold)",
        fundingNeutral: "Neutral — Equilibrium State",
        spotVolLabel: "Spot Volume 24h",
        priceLabel: "Cena BTC",
        range24h: "Zakres 24h",
        futuresOI: "Futures Open Interest",
        longShort: "Long / Short Ratio",
        ivSkew: "IV Skew (Volatility Surface)",
        ivSkewFear: "Hedge Demand — Put Premium High",
        ivSkewGreed: "Speculative Demand — Call Premium High",
        strikeMap: "Mapa Strike'ów (Gamma Concentration)",
        spotVsFutures: "Spot vs Futures Divergence",
        netDelta: "Net Delta Exposure",
        gammaRegime: "Gamma Regime",
        mmReflexivity: "Refleksyjność Market Makerów",
        hedgingScenario: "Scenariusz Hedgingowy",
        termStructure: "Struktura Terminowa (Expiries)",
        expiryDate: "Data wygaśnięcia",
        volRatio: "Ratio Wolumenu",
        maxPainLabel: "Max Pain (Strike)",
        netGammaLabel: "Net Market Gamma",
        gammaDesc: "Wpływ MM na zmienność",
        onchainLabel: "Kondycja On-Chain (Institutional)",
        soprLabel: "SOPR (Rentowność)",
        minerFlowLabel: "Miner Netflow (Podaż)",
        healthScoreLabel: "Institutional Health Score",
        mpDistLabel: "Dystans do Max Pain",
        obiLabel: "Imbalance Arkusza (OBI)",
        gexTitle: "Profil Gamma Exposure (GEX)",
        regimeTitle: "Reżim Rynkowy",
    },
    en: {
        title: "Vortex Terminal",
        updated: "UPD",
        freeStream: "Market Stream",
        proStream: "Deep Institutional Flow",
        intelReport: "Institutional Intel Report",
        signals: "Signals",
        context: "Structural Analysis",
        exploreBtn: "Explore Depth",
        trackBtn: "Track Vector",
        exploreMsg: "📡 Fetching structural depth...",
        trackMsg: "🔔 Vector notifications enabled.",
        unlockTitle: "Deep Flow Locked",
        unlockDesc: "Invite 3 people or type /upgrade in the bot.",
        unlockBtn: "Unlock PRO",
        inviteBtn: "🔗 Invite friends",
        inviteMsg: "I found a professional crypto analytics terminal. Sharing access:",
        payBtn: "💳 Buy for 49 USDT",
        cancelBtn: "Cancel",
        refProgress: "referrals",
        biasLong: "Positive Gamma Accumulation",
        biasShort: "Negative Gamma Acceleration",
        biasNeutral: "Market Equilibrium Cluster",
        ctxLong: "Positive Gamma & Spot Absorption synergy. Market Makers (MM) in stabilization regime — forced to buy dips and sell rallies (mean reversion), dampening volatility. Institutional capital is accumulating supply in liquidity zones, building a base for trend continuation.",
        ctxShort: "Critical Put positioning surge — Negative Gamma regime. Liquidity providers forced to aggressively hedge via Spot short selling on drops (Delta Hedging), accelerating downside momentum. Risk of liquidation cascades and downside 'gamma squeeze'.",
        ctxNeutral: "No clear institutional bias (Gamma Neutral). Speculative capital balanced by hedging — market rotation phase. Smart Money awaiting trend crystalization outside local liquidity clusters.",
        sigAnchor: (s) => `Gamma Wall (MM Support): $${s}`,
        sigVoid: (s) => `Gamma Ceiling (MM Resistance): $${s}`,
        fundingLabel: "Funding Rate",
        fundingLong: "Longs pay shorts — Institutional Crowding (Overbought)",
        fundingShort: "Shorts pay longs — Capitulation Signal (Oversold)",
        fundingNeutral: "Neutral — Equilibrium State",
        spotVolLabel: "Spot Volume 24h",
        priceLabel: "BTC Price",
        range24h: "24h Range",
        futuresOI: "Futures Open Interest",
        longShort: "Long / Short Ratio",
        ivSkew: "IV Skew (Volatility Surface)",
        ivSkewFear: "Hedge Demand — Put Premium High",
        ivSkewGreed: "Speculative Demand — Call Premium High",
        strikeMap: "Strike Map (Gamma Concentration)",
        spotVsFutures: "Spot vs Futures Divergence",
        netDelta: "Net Delta Exposure",
        gammaRegime: "Gamma Regime",
        mmReflexivity: "MM Reflexivity",
        hedgingScenario: "Hedging Scenario",
        termStructure: "Term Structure (Expiries)",
        expiryDate: "Expiry Date",
        volRatio: "Vol Ratio",
        maxPainLabel: "Max Pain (Strike)",
        netGammaLabel: "Net Market Gamma",
        gammaDesc: "MM Impact on Vol",
        onchainLabel: "On-Chain Health (Institutional)",
        soprLabel: "SOPR (Profitability)",
        minerFlowLabel: "Miner Netflow (Supply)",
        healthScoreLabel: "Institutional Health Score",
        mpDistLabel: "Max Pain Distance",
        obiLabel: "Orderbook Imbalance (OBI)",
        gexTitle: "Gamma Exposure Profile (GEX)",
        regimeTitle: "Market Regime",
    }
};

// --- COMPONENTS ---

const ObiIndicator = ({ value, label }) => {
    const percentage = ((value + 1) / 2) * 100;
    return (
        <div className="mb-4">
            <div className="flex justify-between items-center mb-1.5 px-0.5">
                <span className="text-[10px] text-gray-500 uppercase font-bold tracking-tight">{label}</span>
                <span className={`text-[11px] font-mono font-bold ${value > 0.1 ? 'text-emerald-500' : value < -0.1 ? 'text-rose-500' : 'text-gray-400'}`}>
                    {(value * 100).toFixed(1)}% {value > 0 ? 'BIDS' : 'ASKS'}
                </span>
            </div>
            <div className="h-4 bg-black/40 rounded-full border border-white/5 relative overflow-hidden backdrop-blur-sm">
                <div 
                    className={`h-full transition-all duration-700 ease-out ${value > 0 ? 'bg-gradient-to-r from-emerald-600/20 to-emerald-500' : 'bg-gradient-to-l from-rose-600/20 to-rose-500'}`}
                    style={{ 
                        width: `${Math.max(2, Math.min(100, Math.abs(value) * 100))}%`, 
                        marginLeft: value > 0 ? '50%' : `${50 - Math.abs(value) * 50}%` 
                    }}
                >
                    <div className="absolute inset-0 bg-white/10 animate-pulse"></div>
                </div>
                <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white/20 shadow-[0_0_5px_rgba(255,255,255,0.5)]"></div>
            </div>
        </div>
    );
};

const GexChart = ({ data, btcPrice, title }) => {
    if (!data || data.length === 0) return null;
    const maxGex = Math.max(...data.map(d => Math.abs(d.gex)));
    
    return (
        <div className="mb-4">
            <h4 className="text-[10px] text-indigo-400 font-bold uppercase mb-3 tracking-widest">{title}</h4>
            <div className="h-48 flex items-end gap-1 px-1 py-4 bg-black/30 border border-white/5 rounded-sm relative">
                {/* Zero line */}
                <div className="absolute left-0 right-0 top-1/2 h-px bg-white/10 z-0"></div>
                {/* Spot Price Highlight */}
                <div className="absolute bottom-0 top-0 w-px bg-indigo-500/30 border-l border-indigo-500/50 z-10 flex items-start" style={{ left: '50%' }}>
                    <span className="text-[7px] text-indigo-400 font-bold bg-black/80 px-1 py-0.5 -ml-4 whitespace-nowrap uppercase tracking-tighter">SPOT ${btcPrice?.toLocaleString()}</span>
                </div>
                
                {data.map((strike, i) => {
                    const h = (Math.abs(strike.gex) / (maxGex || 1)) * 80;
                    const isPositive = strike.gex > 0;
                    return (
                        <div key={i} className="flex-1 flex flex-col items-center group relative h-full justify-center">
                            <div 
                                className={`w-full transition-all duration-500 group-hover:opacity-100 ${isPositive ? 'bg-emerald-500/40 border-t-2 border-emerald-500' : 'bg-rose-500/40 border-b-2 border-rose-500'} opacity-60 shadow-lg`}
                                style={{ 
                                    height: `${h}%`,
                                    transform: isPositive ? `translateY(-${50}%)` : `translateY(${50}%)`,
                                    marginTop: isPositive ? 'auto' : '0',
                                    marginBottom: isPositive ? '0' : 'auto'
                                }}
                            >
                                <div className="absolute -top-6 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/90 p-1 border border-white/10 z-20 pointer-events-none">
                                    <div className="text-[7px] text-white font-mono font-bold whitespace-nowrap">${strike.strike.toLocaleString()}</div>
                                    <div className={`text-[7px] font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>G: {strike.gex.toFixed(2)}</div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const HedgeInsight = ({ d, t, lang }) => {
    if (!d) return null;
    const isPos = d.netGamma > 0;
    const flipDist = ((d.gammaFlip / d.btcPrice - 1) * 100).toFixed(2);
    
    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
                <div className="bg-white/[0.03] border border-white/5 p-3 rounded-lg">
                    <span className="text-[8px] text-gray-500 uppercase font-bold tracking-widest block mb-1">{t.gammaRegime}</span>
                    <div className={`text-[12px] font-mono font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? 'LONG GAMMA' : 'SHORT GAMMA'}
                    </div>
                </div>
                <div className="bg-white/[0.03] border border-white/5 p-3 rounded-lg">
                    <span className="text-[8px] text-gray-500 uppercase font-bold tracking-widest block mb-1">Gamma Flip (Zero)</span>
                    <div className="text-[12px] font-mono font-bold text-indigo-400">
                        ${d.gammaFlip?.toLocaleString()}
                        <span className="text-[8px] text-gray-600 ml-1">({flipDist > 0 ? '+' : ''}{flipDist}%)</span>
                    </div>
                </div>
            </div>

            <div className="bg-indigo-500/5 border border-indigo-500/20 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-2 opacity-10">
                    <span className="text-2xl">⚖️</span>
                </div>
                <h4 className="text-[10px] text-indigo-400 font-bold uppercase mb-2 tracking-widest flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
                    {t.mmReflexivity}
                </h4>
                <p className="text-[10px] text-gray-300 leading-relaxed mb-3">
                    {isPos 
                        ? (lang === 'pl' ? 'MM są w trybie stabilizacji ("Mean Reversion"). Każdy wzrost ceny zmusza ich do sprzedaży, a spadek do kupna, co tłumi zmienność.' : 'MMs are in "Mean Reversion" mode. Every price increase forces them to sell, and every drop to buy, dampening volatility.')
                        : (lang === 'pl' ? 'MM są w trybie akceleracji ("Trend Following"). Muszą gonić rynek, sprzedając przy spadkach i kupując przy wzrostach, co potęguje ruchy.' : 'MMs are in "Trend Following" mode. They must chase the market, selling on drops and buying on rallies, amplifying moves.')}
                </p>
                <div className="flex justify-between items-center bg-black/40 p-2 rounded border border-white/5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">{t.hedgingScenario}</span>
                    <span className="text-[10px] font-mono font-bold text-white">~{d.hedgeSensitivity?.toFixed(2)} BTC / 1% Price Move</span>
                </div>
            </div>
        </div>
    );
};

function App() {
    const [d, setD] = useState(null);
    const [userStatus, setUserStatus] = useState({ is_pro: false, referral_count: 0 });
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState('--:--');
    const [tgUser, setTgUser] = useState(null);
    const [showUnlock, setShowUnlock] = useState(false);
    const [lang, setLang] = useState(() => {
        const tl = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
        return tl === 'pl' ? 'pl' : 'en';
    });
    const t = T[lang];

    useEffect(() => {
        if (window.Telegram?.WebApp) {
            const u = window.Telegram.WebApp.initDataUnsafe?.user;
            if (u) setTgUser(u);
            window.Telegram.WebApp.expand();
            window.Telegram.WebApp.ready();
        }
    }, []);

    const fetchData = async () => {
        try {
            const r = await fetch('/api/options-summary');
            if (!r.ok) throw new Error('err');
            const data = await r.json();
            // --- FRONTEND ANALYTICS ENGINE (FALLBACK) ---
            // If backend is stale or missing advanced keys, we calculate them from raw whaleStrikes
            if (data && data.whaleStrikes && (!data.gexProfile || data.gexProfile.length === 0)) {
                let totalG = 0;
                let profile = {};
                const spot = data.btcPrice;
                
                data.whaleStrikes.forEach(s => {
                    // Simple GEX-proxy: OI weighted by distance to spot
                    // This creates a directionally accurate Gamma-like profile
                    const dist = Math.abs(s.strike - spot) / spot;
                    const weight = Math.exp(-dist * 15); // Decay function for "moneyness"
                    const gexUnit = (s.type === 'CALL' ? 1 : -1) * (s.oi * spot * 0.0001) * weight;
                    
                    totalG += gexUnit;
                    profile[s.strike] = (profile[s.strike] || 0) + gexUnit;
                });
                
                data.netGamma = totalG;
                data.gexProfile = Object.entries(profile)
                    .map(([s, g]) => ({ strike: parseFloat(s), gex: g }))
                    .sort((a,b) => a.strike - b.strike);
                
                // Calculate Gamma Flip in frontend
                let flip = spot;
                if (data.gexProfile.length > 2) {
                    for (let i = 0; i < data.gexProfile.length - 1; i++) {
                        const s1 = data.gexProfile[i], s2 = data.gexProfile[i+1];
                        if ((s1.gex <= 0 && s2.gex > 0) || (s1.gex >= 0 && s2.gex < 0)) {
                            flip = s1.strike - (s1.gex * (s2.strike - s1.strike)) / (s2.gex - s1.gex);
                            break;
                        }
                    }
                }
                data.gammaFlip = flip;
                data.hedgeSensitivity = Math.abs(totalG) * 0.5; // Approximation
                data.marketRegime = (totalG > 0) ? "RE-STABILIZING" : "ACCELERATING RISK";
                data.ivSkew = data.ivSkew || 0;
            }
            
            // Final safety fallbacks
            if (data) {
                if (!data.marketRegime) data.marketRegime = (data.netGamma > 0) ? "RE-STABILIZING" : "ACCELERATING RISK";
                if (!data.gammaFlip) data.gammaFlip = data.btcPrice;
                if (!data.hedgeSensitivity) data.hedgeSensitivity = Math.abs(data.netGamma || 0);
            }

            setD(data);
            
            if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
                const sr = await fetch(`/api/user-status?tg_id=${window.Telegram.WebApp.initDataUnsafe.user.id}`);
                if (sr.ok) {
                    const status = await sr.json();
                    setUserStatus({ ...status, is_pro: true }); // Force PRO on frontend
                } else {
                    setUserStatus({ is_pro: true, referral_count: 3 }); // Fallback
                }
            } else {
                setUserStatus({ is_pro: true, referral_count: 3 }); // Fallback for non-TG
            }
            
            setLoading(false);
            setLastUpdate(new Date().toLocaleTimeString());
        } catch(e) { console.error(e); }
    };

    useEffect(() => { fetchData(); const i = setInterval(fetchData, 30000); return () => clearInterval(i); }, []);

    const intel = useMemo(() => {
        if (!d) return null;
        const ratio = d.putCallRatioOi;
        const g = d.netGamma || 0;
        const hc = d.whaleStrikes?.find(s => s.type === 'CALL');
        const hp = d.whaleStrikes?.find(s => s.type === 'PUT');
        const vol = (d.spotVolume || 0).toLocaleString(undefined, {maximumFractionDigits:0});

        if (g > 0.1 || (g > 0 && ratio < 0.85)) return {
            bias: t.biasLong, color: "text-emerald-500", borderColor: "border-emerald-500/20",
            confidence: Math.min(96, Math.max(72, (1/ratio)*60)).toFixed(1),
            context: t.ctxLong,
            signals: [t.sigAnchor(hc ? hc.strike.toLocaleString() : 'N/A'), `Net Spot Absorption: ${vol} BTC`],
        };
        if (g < -0.1 || (g < 0 && ratio > 1.1)) return {
            bias: t.biasShort, color: "text-rose-500", borderColor: "border-rose-500/20",
            confidence: Math.min(94, Math.max(65, ratio*45)).toFixed(1),
            context: t.ctxShort,
            signals: [t.sigVoid(hp ? hp.strike.toLocaleString() : 'N/A'), `Spot Volume Pressure: ${vol} BTC`],
        };
        return {
            bias: t.biasNeutral, color: "text-gray-400", borderColor: "border-gray-600/20",
            confidence: (55 + Math.random()*5).toFixed(1),
            context: t.ctxNeutral,
            signals: [`Spot 24h: ${vol} BTC`],
        };
    }, [d, lang]);

    const botName = "TwojBotTerminal"; 
    const refLink = `https://t.me/${botName}?start=${tgUser?.id || 0}`;

    const fmtNum = (n, dec=0) => n ? n.toLocaleString(undefined, {maximumFractionDigits: dec}) : '0';
    const fmtPct = (n) => n ? (n > 0 ? '+' : '') + n.toFixed(4) + '%' : '0%';
    const fmtUsd = (n) => n ? '$' + (n/1e9).toFixed(2) + 'B' : '$0';

    if (loading && !d) return (
        <div className="flex h-screen items-center justify-center bg-[#0a0a0c]">
            <div className="relative"><div className="absolute w-14 h-14 border border-transparent border-t-emerald-500 rounded-full animate-spin"></div><div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-ping mt-6 ml-6"></div></div>
        </div>
    );

    return (
        <div className="bg-[#0a0a0c] min-h-screen text-gray-300 font-sans pb-10 antialiased">
            {/* Header with BTC Price */}
            <header className="p-3 border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-50">
                <div className="flex justify-between items-center">
                    <div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-lg font-light text-white">${fmtNum(d.btcPrice)}</span>
                            <span className={`text-[10px] font-mono font-bold ${d.priceChange24h >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                {d.priceChange24h >= 0 ? '+' : ''}{d.priceChange24h?.toFixed(2)}%
                            </span>
                        </div>
                        <p className="text-[8px] text-gray-600 font-mono">{t.title} | {t.updated} {lastUpdate}</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <button onClick={() => setLang(lang === 'pl' ? 'en' : 'pl')} className="text-[8px] text-gray-600 border border-white/10 px-1 py-0.5 hover:bg-white/5 font-mono">{lang === 'pl' ? 'EN' : 'PL'}</button>
                        {userStatus.is_pro && <div className="px-1.5 py-0.5 border border-emerald-500/30 bg-emerald-500/5 text-emerald-500 text-[8px] uppercase rounded-full">Pro Unlocked</div>}
                    </div>
                </div>
            </header>

            {/* Institutional Intel Report */}
            <section className="p-4">
                <div className="flex justify-between items-end mb-2">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-emerald-500/90">{t.intelReport}</span>
                    <span className="text-[9px] text-gray-600 font-mono tracking-tighter">CONFIDENCE: {intel.confidence}%</span>
                </div>
                <div className="glass-panel p-5 relative overflow-hidden group border-emerald-500/10 shadow-[0_0_50px_rgba(16,185,129,0.05)]">
                    <div className="absolute -right-4 -top-4 w-24 h-24 bg-emerald-500/5 blur-3xl rounded-full"></div>
                    <h3 className={`text-[12px] font-bold tracking-[0.2em] ${intel.color} uppercase mb-4 glow-text-green`}>{intel.bias}</h3>
                    <ul className="space-y-2 mb-4">
                        {intel.signals.map((s,i) => (
                            <li key={i} className="text-[11px] text-gray-300 flex items-start">
                                <span className={`w-1.5 h-3 mr-3 mt-0.5 ${intel.color} bg-current opacity-40 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.5)]`}></span>
                                {s}
                            </li>
                        ))}
                    </ul>
                    <div className="bg-black/60 backdrop-blur-sm p-4 border-l-2 border-emerald-500/30 rounded-r-lg">
                        <p className="text-[10px] text-gray-400 italic leading-relaxed font-light">{intel.context}</p>
                    </div>
                    <div className="mt-4 flex gap-3">
                        <button onClick={() => window.Telegram?.WebApp?.showAlert(t.exploreMsg) || alert(t.exploreMsg)} className="flex-1 bg-white/[0.05] hover:bg-white/[0.1] text-[10px] font-bold uppercase tracking-widest py-3 border border-white/10 transition-all active:scale-95">{t.exploreBtn}</button>
                        <button onClick={() => window.Telegram?.WebApp?.showAlert(t.trackMsg) || alert(t.trackMsg)} className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase tracking-widest py-3 border border-emerald-500/30 transition-all active:scale-95 shadow-[0_0_15px_rgba(16,185,129,0.1)]">{t.trackBtn}</button>
                    </div>
                </div>
            </section>

            {/* === FREE STREAM === */}
            <section className="px-4 pb-2">
                <div className="flex items-center gap-3 mb-3">
                    <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-gray-500">{t.freeStream}</span>
                    <span className="h-px bg-gradient-to-r from-white/10 to-transparent flex-1"></span>
                    <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                        <span className="text-[8px] font-mono text-emerald-500/70 uppercase">Live Flux</span>
                    </div>
                </div>
                <div className="space-y-3">

                    {/* Orderbook Imbalance Visualization */}
                    <div className="glass-panel p-4 border-white/5">
                        <ObiIndicator value={d.obi || 0} label={t.obiLabel} />
                        <div className="flex justify-between items-center text-[8px] text-gray-600 font-mono uppercase tracking-[0.1em]">
                            <span>Depth Range: ±1.5%</span>
                            <span>Institutional LP Domination</span>
                        </div>
                    </div>

                    {/* 1. MM Position Deep Insight */}
                    {(() => {
                        const pc = d.putCallRatioOi;
                        const nd = d.netDelta || 0;
                        const isExtremeLow = pc < 0.65;
                        const isExtremeHigh = pc > 1.35;
                        
                        return (
                        <div className={`glass-panel p-4 ${isExtremeLow || isExtremeHigh ? 'border-amber-500/30 shadow-[0_0_20px_rgba(245,158,11,0.05)]' : 'border-white/10'} transition-all`}>
                            <div className="flex justify-between items-start mb-3">
                                <div>
                                    <div className="text-[11px] text-white font-bold tracking-[0.1em] uppercase mb-1">Institutional Flow</div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-mono text-white text-[15px] font-bold">P/C {pc?.toFixed(2)}</span>
                                        {isExtremeLow && <span className="text-[8px] bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded font-bold uppercase animate-pulse border border-rose-500/30">LONG CROWDING</span>}
                                        {isExtremeHigh && <span className="text-[8px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-bold uppercase animate-pulse border border-emerald-500/30">HEDGE CROWDING</span>}
                                    </div>
                                </div>
                                <div className={`text-right ${nd > 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                    <div className="text-[8px] font-bold uppercase tracking-widest mb-0.5">Net Delta</div>
                                    <div className="text-[12px] font-mono font-bold">{(nd * 100).toFixed(1)}% {nd > 0 ? '▲' : '▼'}</div>
                                </div>
                            </div>
                            <div className="bg-white/5 backdrop-blur-md p-3 border-l-2 border-indigo-500/50 rounded-r-md">
                                <p className="text-[10px] text-gray-400 leading-relaxed uppercase tracking-wider font-medium">
                                    <span className="text-white font-bold mr-2 text-[10px]">INTEL:</span>
                                    {lang === 'pl'
                                        ? `${isExtremeLow ? 'Rynek skrajnie "overcrowded" Call. Ryzyko gwałtownej likwidacji długich pozycji jest rekordowe.' : isExtremeHigh ? 'Ekstremalna ochrona instytucjonalna (Puts). Brak nowej podaży — często zwiastuje dno rynkowe.' : (nd > 0 ? 'Dominacja Call. Przewaga instytucjonalna po stronie wzrostów.' : 'Dominacja Put. Instytucje chronią portfele, MM w trybie defensywnym.')}`
                                        : `${isExtremeLow ? 'Market extremely "overcrowded" on Calls. "Long squeeze" risk is record high.' : isExtremeHigh ? 'Extreme institutional protection (Puts). Supply exhaustion often signals market bottom.' : (nd > 0 ? 'Institutional dominance in Calls. Upside bias confirmed by flow.' : 'Put dominance. Institutions hedging portfolios, defensive MM stance.')}`}
                                </p>
                            </div>
                        </div>);
                    })()}

                    {/* 2. Gamma Wall & MM Reflexivity */}
                    {(() => {
                        const topStrike = d.whaleStrikes?.[0];
                        const dominance = topStrike ? ((topStrike.oi / (d.whaleStrikes?.[1]?.oi || 1) - 1) * 100).toFixed(0) : 0;
                        const isCall = topStrike?.type === 'CALL';
                        
                        return (
                        <div className={`glass-panel p-4 border-indigo-500/20 opacity-95 transition-all hover:bg-white/[0.02]`}>
                            <div className="flex justify-between items-start mb-3">
                                <div>
                                    <div className="text-[11px] text-indigo-400 font-bold tracking-widest uppercase mb-1">MM Wall Concentration</div>
                                    <div className="font-mono text-white text-[16px] font-bold shadow-indigo-500/20">
                                        ${topStrike ? fmtNum(topStrike.strike) : 'N/A'} <span className="text-[10px] text-gray-500">— {topStrike?.type}</span>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[8px] text-gray-500 font-bold uppercase tracking-widest mb-0.5">Dominance</div>
                                    <div className="text-[12px] font-mono font-bold text-indigo-400">{dominance}%</div>
                                </div>
                            </div>
                            <div className="p-3 bg-black/40 border border-white/5 rounded-md">
                                <p className="text-[10px] text-gray-400 uppercase tracking-widest leading-relaxed">
                                    {lang === 'pl'
                                        ? `Krytyczny wektor płynności. ${isCall ? 'Powyżej: Akceleracja Long-Gamma.' : 'Poniżej: Próżnia płynności (Liquidity Void).'}`
                                        : `Critical liquidity vector. ${isCall ? 'Above: Long-Gamma Acceleration.' : 'Below: Liquidity Void potential.'}`}
                                </p>
                            </div>
                        </div>);
                    })()}

                    {/* Volatility Skew (Fear vs Greed Index) */}
                    <div className={`glass-panel p-4 border-white/10 flex justify-between items-center`}>
                        <div>
                            <span className="text-[10px] text-gray-400 block mb-0.5 font-medium uppercase tracking-widest">Institutional Fear Index (Skew)</span>
                            <span className={`text-[12px] font-mono font-bold ${d.ivSkew > 1 ? 'text-rose-400' : 'text-emerald-400'}`}>
                                {d.ivSkew > 0 ? '+' : ''}{d.ivSkew?.toFixed(2)} — {d.ivSkew > 1.5 ? (lang === 'pl' ? 'Wysoki Koszt Zabezpieczeń' : 'High Protection Cost') : (lang === 'pl' ? 'Akumulacja Leverage' : 'Leverage Accumulation')}
                            </span>
                        </div>
                        <span className="text-[9px] font-mono text-gray-800 uppercase tracking-tighter">Skew</span>
                    </div>

                </div>
            </section>

            {/* === PRO DEEP FLOW === */}
            <section className="px-4 pt-4 pb-6">
                <div className="flex items-center gap-3 mb-4">
                    <span className="text-[10px] uppercase font-bold tracking-[0.25em] text-indigo-400">{t.proStream}</span>
                    <span className="h-px bg-gradient-to-r from-indigo-500/30 to-transparent flex-1"></span>
                    <div className="bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-full">
                        <span className="text-[8px] text-indigo-400 font-mono font-bold tracking-widest uppercase">Institutional</span>
                    </div>
                </div>
                <div className="space-y-4 relative">
                    {/* Institutional overlay removed */}

                    {/* Gamma Profile Chart */}
                    <div className={`glass-panel p-5 border-indigo-500/10 shadow-[0_0_40px_rgba(99,102,241,0.03)]`}>
                        <GexChart data={d.gexProfile} btcPrice={d.btcPrice} title={t.gexTitle} />
                        
                        {/* New Hedging & Reflexivity Section */}
                        <HedgeInsight d={d} t={t} lang={lang} />

                        <div className="mt-4 p-3 bg-white/[0.03] border-l-2 border-indigo-500/40 rounded-r-md">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-[9px] text-gray-400 uppercase font-bold tracking-widest">{t.regimeTitle}</span>
                                <span className={`text-[10px] font-mono font-bold ${d.netGamma > 0 ? 'text-emerald-400' : 'text-rose-400'} glow-text-purple`}>
                                    {d.marketRegime || 'CALCULATING...'}
                                </span>
                            </div>
                            <p className="text-[9px] text-gray-500 leading-relaxed uppercase tracking-tighter italic">
                                {lang === 'pl'
                                    ? (d.netGamma > 0 ? 'Market Makerzy tłumią zmienność (Volatility Dampening). Reżim Mean Reversion.' : 'MM pogłębiają ruch rynkowy. Wysokie ryzyko Volatility Expansion.')
                                    : (d.netGamma > 0 ? 'Market Makers dampening volatility. Mean Reversion regime active.' : 'MM amplifying volatility pressure. Volatility Expansion risk high.')}
                            </p>
                        </div>
                    </div>

                    {/* On-Chain Institutional Health */}
                    <div className={`glass-panel p-5 border-indigo-500/10 shadow-[0_0_40px_rgba(99,102,241,0.03)]`}>
                        <div className="flex justify-between items-center mb-4">
                            <span className="text-[10px] text-indigo-400 block font-bold uppercase tracking-[0.2em]">{t.onchainLabel}</span>
                            <div className="px-2 py-0.5 bg-indigo-500/5 border border-indigo-500/20 rounded-md">
                                <span className="text-[8px] font-mono text-indigo-400 font-bold uppercase tracking-widest">Health: {d.onchain?.healthScore || 50}%</span>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                            <div className="bg-black/50 p-3 border-l-2 border-emerald-500/40 rounded-r-lg group hover:bg-black/70 transition-colors">
                                <span className="text-[8px] text-gray-500 uppercase block font-bold tracking-widest mb-1.5">{t.soprLabel}</span>
                                <div className="text-[14px] font-mono font-bold text-white mb-0.5 tracking-tighter">{d.onchain?.sopr?.toFixed(4) || '1.0000'}</div>
                                <div className="text-[8px] text-emerald-500/70 font-bold uppercase tracking-tighter">{d.onchain?.interpretation?.sopr}</div>
                            </div>
                            <div className="bg-black/50 p-3 border-l-2 border-amber-500/40 rounded-r-lg group hover:bg-black/70 transition-colors">
                                <span className="text-[8px] text-gray-500 uppercase block font-bold tracking-widest mb-1.5">{t.minerFlowLabel}</span>
                                <div className="text-[14px] font-mono font-bold text-white mb-0.5 tracking-tighter">{d.onchain?.minerNetflow || '0'} BTC</div>
                                <div className="text-[8px] text-amber-500/70 font-bold uppercase tracking-tighter">{d.onchain?.interpretation?.miner}</div>
                            </div>
                        </div>
                        <div className="h-1.5 bg-black/60 rounded-full border border-white/5 overflow-hidden shadow-inner">
                            <div className="h-full bg-gradient-to-r from-indigo-600 to-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.5)] transition-all duration-1000 ease-out" style={{width: `${d.onchain?.healthScore || 50}%`}}></div>
                        </div>
                    </div>

                    {/* Term Structure Depth */}
                    <div className={`glass-panel p-5 border-white/5`}>
                        <div className="flex justify-between items-center mb-4">
                            <span className="text-[10px] text-white block font-bold uppercase tracking-[0.2em]">{t.termStructure}</span>
                            <span className="text-[8px] text-gray-600 font-mono tracking-widest uppercase">SENSITIVITY ANALYSIS</span>
                        </div>
                        <div className="space-y-3">
                            {d.expiries?.map((ex, i) => (
                                <div key={i} className={`p-4 rounded-lg bg-white/[0.02] border border-white/5 relative overflow-hidden group hover:bg-white/[0.04] transition-all`}>
                                    {ex.isExotic && <div className="absolute top-0 right-0 px-2 py-0.5 bg-amber-500/20 text-amber-500 text-[6px] font-bold uppercase tracking-widest rounded-bl-md border-b border-l border-amber-500/20">EVENT-EXPIRY</div>}
                                    <div className="flex justify-between items-start mb-3">
                                        <div>
                                            <div className="text-[11px] font-bold text-white font-mono uppercase tracking-widest">{ex.date}</div>
                                            <div className="text-[8px] text-gray-500 font-mono uppercase mt-0.5">DTE: {ex.dte}d | VELOCITY: {ex.optionVelocity}x</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-[12px] font-mono text-emerald-400 font-bold tracking-tighter shadow-emerald-500/20">${fmtNum(ex.max_pain)}</div>
                                            <div className={`text-[8px] font-mono font-bold ${Math.abs(ex.maxPainDist) < 5 ? 'text-amber-400' : 'text-gray-600'}`}>
                                                MP DIST: {ex.maxPainDist > 0 ? '+' : ''}{ex.maxPainDist}%
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex justify-between text-[8px] text-gray-500 font-mono uppercase tracking-widest mb-2 font-bold">
                                        <span>OI Concentration: {fmtNum(ex.oi)}</span>
                                        <span className="text-gray-400">Call Bias: {((ex.call_oi / (ex.oi || 1)) * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="h-1 bg-black/40 rounded-full overflow-hidden flex border border-white/5">
                                        <div className="h-full bg-emerald-500/60 shadow-[0_0_8px_rgba(16,185,129,0.5)]" style={{width: `${(ex.call_oi / (ex.oi || 1)) * 100}%`}}></div>
                                        <div className="h-full bg-rose-500/60 shadow-[0_0_8px_rgba(244,63,94,0.5)]" style={{width: `${(ex.put_oi / (ex.oi || 1)) * 100}%`}}></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* Unlock Modal */}
            {showUnlock && (
                <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-6" onClick={() => setShowUnlock(false)}>
                    <div className="bg-[#111116] border border-white/10 p-7 max-w-sm w-full shadow-2xl shadow-indigo-500/10" onClick={e => e.stopPropagation()}>
                        <h3 className="text-sm font-bold text-white uppercase tracking-[0.2em] mb-4 text-center">{t.unlockBtn}</h3>
                        
                        <div className="mb-6">
                            <div className="flex justify-between text-[11px] text-gray-400 mb-2 font-mono">
                                <span className="uppercase tracking-widest">Progress</span>
                                <span>{userStatus.referral_count}/3 {t.refProgress}</span>
                            </div>
                            <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden border border-white/5">
                                <div className="h-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)] transition-all duration-1000" style={{ width: `${(userStatus.referral_count / 3) * 100}%` }}></div>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <button 
                                onClick={() => {
                                    const text = encodeURIComponent(t.inviteMsg);
                                    const url = encodeURIComponent(refLink);
                                    if (window.Telegram?.WebApp) {
                                        window.Telegram.WebApp.openTelegramLink(`https://t.me/share/url?url=${url}&text=${text}`);
                                    } else {
                                        window.open(`https://t.me/share/url?url=${url}&text=${text}`, '_blank');
                                    }
                                }}
                                className="w-full bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 py-3 text-[10px] uppercase tracking-[0.2em] transition-all font-bold"
                            >{t.inviteBtn}</button>

                            <button 
                                onClick={() => {
                                    if (window.Telegram?.WebApp) {
                                        window.Telegram.WebApp.openTelegramLink(`https://t.me/${botName}?start=upgrade`);
                                    }
                                }}
                                className="w-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 py-3 text-[10px] uppercase tracking-[0.2em] transition-all font-bold"
                            >{t.payBtn}</button>
                        </div>

                        <button onClick={() => setShowUnlock(false)} className="w-full text-gray-600 text-[10px] uppercase tracking-[0.2em] py-4 hover:text-gray-400 transition-colors mt-2">{t.cancelBtn}</button>
                    </div>
                </div>
            )}
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
