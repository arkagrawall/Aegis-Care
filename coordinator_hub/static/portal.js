/* Aegis Saathi care portal: coordinator (Today, People), operations (Overview, Alert accuracy, Access log).
   Plain JavaScript, no dependencies. Hash routes give every screen a link (#/today/SR-1070) and a working
   browser Back. Every dynamic string goes through esc(): notes and transcripts are user-written. */
(() => {
"use strict";

// ------------------------------------------------------------------------------------------ strings
const T = {
  en: {
    appName: "Aegis Saathi", tagline: "Care portal",
    signInTitle: "Sign in", signInSub: "Use the code and PIN from your organisation.",
    coordinator: "Care coordinator", operations: "Operations", role: "I am a", code: "Staff code", pin: "PIN",
    showPin: "Show PIN", hidePin: "Hide PIN", go: "Sign in", signingIn: "Signing in…",
    wrong: "That code and PIN don't match. Check both and try again.", needBoth: "Enter your staff code and PIN.",
    samples: "Sample accounts (evaluation build)", familyQ: "Family member?", familyLink: "Open the family view",
    storyTitle: "See who needs care today, before it becomes an emergency.",
    storyText: "Saathi compares each person with their own normal and turns watch readings, check-in calls and medicines into one short list.",
    p1: "Prioritised daily list with the reasons in plain words", p2: "Voice check-in calls in Hindi and English", p3: "Emergency and fall alerts with response tracking",
    signOut: "Sign out", account: "Account", language: "Language",
    today: "Today", people: "People", overview: "Overview", accuracy: "Alert accuracy", audit: "Access log",
    search: "Search name or city", openSearch: "Search", closeSearch: "Close search",
    morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening",
    updated: "Updated", justNow: "just now",
    all: "All", urgent: "Urgent", attention: "Needs attention", watch: "Watch", stable: "Stable",
    showStable: "Show {n} stable", hideStable: "Hide stable",
    nobody: "No one matches", nobodySub: "Try another name or clear the filter.", clearFilter: "Clear filter",
    allCalm: "Everyone is stable today", allCalmSub: "No one needs a call right now. Saathi keeps checking in the background.",
    back: "Back to list", priority: "Priority", outOf: "of 100",
    callNow: "Start check-in call", logFollow: "Log follow-up",
    nextStep: "Suggested next step", whyList: "Why they're on your list", readings: "Health readings", activity: "Recent activity",
    fromCall: "Heard in a check-in call", fromModel: "Saathi pattern model", downWeighted: "Weighted lower after team feedback",
    confHIGH: "High confidence", confMEDIUM: "Medium confidence", confLOW: "Low confidence",
    steps: "Steps", heart: "Heart rate", oxygen: "Blood oxygen", bp: "Blood pressure", sugar: "Blood sugar", weight: "Weight", sleep: "Sleep",
    avg14: "14-day average", lastRec: "Last recorded", notRec: "Not recorded", fewPts: "Not enough readings for a trend",
    src_watch: "Smartwatch", src_demo: "Sample data", src_synthetic: "Sample data", src_manual: "Entered by the care team", src_phone: "Phone app", src_none: "No device connected",
    synced: "synced", nothingYet: "No calls, alerts or follow-ups in the last 14 days.",
    callWord: "Check-in call", mood_good: "In good spirits", mood_okay: "Okay", mood_low: "Feeling low", mood_distressed: "Distressed", concernsW: "To follow up", encouragedW: "Saathi encouraged", alertWord: "Emergency alert", followWord: "Follow-up", transcript: "Show conversation",
    st_completed: "Completed", st_missed: "No answer", st_declined: "Declined", st_connected: "In progress", st_ringing: "Ringing", st_initiated: "Started",
    st_active: "Open", st_confirmed: "Confirmed", st_false_alarm: "False alarm", st_cancelled_by_senior: "Cancelled by them", st_resolved: "Resolved",
    cuesNone: "No symptoms mentioned",
    sosBar: "Emergency alert", confirm: "Confirm emergency", falseAlarm: "Mark false alarm", resolvedT: "Alert updated",
    src_fall_need_help: "Fall detected, asked for help", src_fall_no_response: "Fall detected, no answer for 30 seconds", src_senior_hold: "SOS button on their phone", src_voice_note: "Said it in a voice note", src_call: "Said it on the Saathi call", src_missed_call: "Missed calls to the help number (basic phone)",
    schedTitle: "Daily check-in call", schedNone: "No daily call yet. Saathi can call at the same time every day.", schedAdd: "Add time", schedEvery: "Every day at {t}", schedRemove: "Remove {t}", schedSaved: "Daily call set for {t}", schedRemoved: "Daily call removed", schedLast: "Last call {w}",
    calling: "Calling", ringingT: "Ringing on their phone…", connected: "Connected. Saathi is talking with them.",
    declined: "They declined the call", missed: "No answer", completedT: "Check-in complete", offline: "Their phone is offline, so the call could not ring. Try again later or phone them directly.",
    cues: "Symptoms mentioned", meds: "Medicine", taken: "Taken", skipped: "Not taken", unknown: "Not confirmed", escalated: "Flagged for you to follow up", close: "Close", done: "Done",
    followTitle: "Log follow-up", action: "What did you do?", outcome: "What did you find?", useful: "Was this alert useful?",
    useYes: "Useful", useNo: "Not useful", useRoutine: "Routine", notes: "Notes", notesHelp: "Optional. Visible to your team.", save: "Save follow-up", cancel: "Cancel",
    thanks: "Follow-up saved. Saathi will use it to rank alerts better.",
    act_call_completed: "Called them", act_nurse_dispatched: "Sent a nurse or visit", act_med_reviewed: "Reviewed medicines",
    out_no_issue: "No issue", out_issue_confirmed: "Issue confirmed", out_escalated: "Escalated",
    fb_useful: "Useful", fb_not_useful: "Not useful", fb_routine: "Routine",
    allPeople: "All people", peopleSub: "Everyone assigned to you, most urgent first.",
    colName: "Name", colStatus: "Status", colCity: "City", colAge: "Age", colReason: "Top reason",
    opsSub: "Across all coordinators and cities", monitored: "People monitored", needToday: "Need attention today", openAlerts: "Open emergency alerts",
    avgResp: "Avg. emergency response", followRate: "Alerts followed up", minutes: "min",
    workload: "Workload by coordinator", byCity: "By city", total: "Total",
    emergencies: "Emergency alerts", falls: "Fall detection", calls: "Check-in calls", followUps: "Follow-ups", learning: "Learning from feedback",
    totalAlerts: "Total", confirmedN: "Confirmed", falseN: "False alarms", cancelledN: "Cancelled by them",
    fTriggers: "Times triggered", fOk: "They were fine", fFellOk: "Fell but OK", fHelp: "Asked for help", fNoAns: "No answer",
    cEsc: "Flagged for follow-up", ratings: "Ratings from coordinators", noRatings: "No ratings yet. Ratings on follow-ups tune which reasons count most.",
    accSub: "How well Saathi finds people who are getting worse, and how early",
    catchRate: "Decline caught", precisionK: "Alerts that were real", earlyDays: "Early warning", falsePerWk: "False alerts",
    daysEarly: "days before it became serious (median)", perCoordWk: "per coordinator per week", ofCases: "of {n} decline cases",
    compare: "How each part contributes", rulesOnly: "Personal-baseline rules", modelOnly: "Pattern model", combined: "Saathi (combined)",
    langTitle: "Understanding what people say", langSub: "Symptoms recognised in Hindi, Hinglish and English sentences",
    trainedOn: "Model trained on", personDays: "person-days of readings", coverage: "Usable watch data", coverageSub: "of days have enough readings to score",
    method: "Methodology and limits", threshold: "Alert threshold: priority {n} or higher.",
    when: "When", who: "Who", did: "Action", target: "Record", auditSub: "Every view and change of a person's record", roleStaff: "Coordinator", roleOps: "Operations", roleFamily: "Family",
    loadFail: "Couldn't load this page", loadFailSub: "Check your connection. We'll keep retrying.", retry: "Try again",
    summaryLine: "{a} need you today", summaryUrgent: "{n} urgent", summaryNone: "No one needs a call right now",
  },
  hi: {
    appName: "एजिस साथी", tagline: "केयर पोर्टल",
    signInTitle: "साइन इन", signInSub: "अपनी संस्था से मिला कोड और पिन डालें।",
    coordinator: "केयर कोऑर्डिनेटर", operations: "ऑपरेशन्स", role: "मैं हूँ", code: "स्टाफ़ कोड", pin: "पिन",
    showPin: "पिन दिखाएं", hidePin: "पिन छिपाएं", go: "साइन इन", signingIn: "साइन इन हो रहा है…",
    wrong: "कोड और पिन मेल नहीं खाते। दोनों जाँचकर फिर कोशिश करें।", needBoth: "स्टाफ़ कोड और पिन डालें।",
    samples: "नमूना खाते (मूल्यांकन संस्करण)", familyQ: "परिवार के सदस्य?", familyLink: "परिवार वाला पेज खोलें",
    storyTitle: "आज किसे देखभाल चाहिए, यह आपात स्थिति बनने से पहले जानें।",
    storyText: "साथी हर व्यक्ति की तुलना उनके अपने सामान्य से करता है और घड़ी की रीडिंग, चेक-इन कॉल और दवाओं को एक छोटी सूची में बदलता है।",
    p1: "सरल शब्दों में कारणों के साथ रोज़ की प्राथमिकता सूची", p2: "हिंदी और अंग्रेज़ी में वॉइस चेक-इन कॉल", p3: "आपातकाल और गिरने के अलर्ट, जवाब की निगरानी के साथ",
    signOut: "साइन आउट", account: "खाता", language: "भाषा",
    today: "आज", people: "लोग", overview: "सारांश", accuracy: "अलर्ट की सटीकता", audit: "एक्सेस लॉग",
    search: "नाम या शहर खोजें", openSearch: "खोजें", closeSearch: "खोज बंद करें",
    morning: "सुप्रभात", afternoon: "नमस्ते", evening: "शुभ संध्या",
    updated: "अपडेट", justNow: "अभी",
    all: "सभी", urgent: "अत्यावश्यक", attention: "ध्यान चाहिए", watch: "नज़र रखें", stable: "स्थिर",
    showStable: "{n} स्थिर दिखाएं", hideStable: "स्थिर छिपाएं",
    nobody: "कोई मेल नहीं खाता", nobodySub: "दूसरा नाम आज़माएं या फ़िल्टर हटाएं।", clearFilter: "फ़िल्टर हटाएं",
    allCalm: "आज सब स्थिर हैं", allCalmSub: "अभी किसी को कॉल की ज़रूरत नहीं। साथी पीछे से जाँच करता रहता है।",
    back: "सूची पर वापस", priority: "प्राथमिकता", outOf: "100 में से",
    callNow: "चेक-इन कॉल शुरू करें", logFollow: "फ़ॉलो-अप दर्ज करें",
    nextStep: "सुझाया गया अगला कदम", whyList: "ये आपकी सूची में क्यों हैं", readings: "सेहत की रीडिंग", activity: "हाल की गतिविधि",
    fromCall: "चेक-इन कॉल में सुना गया", fromModel: "साथी पैटर्न मॉडल", downWeighted: "टीम की राय के बाद कम वज़न",
    confHIGH: "ऊँचा भरोसा", confMEDIUM: "मध्यम भरोसा", confLOW: "कम भरोसा",
    steps: "कदम", heart: "धड़कन", oxygen: "ऑक्सीजन", bp: "ब्लड प्रेशर", sugar: "शुगर", weight: "वज़न", sleep: "नींद",
    avg14: "14 दिन का औसत", lastRec: "आख़िरी बार दर्ज", notRec: "दर्ज नहीं", fewPts: "रुझान के लिए पर्याप्त रीडिंग नहीं",
    src_watch: "स्मार्टवॉच", src_demo: "नमूना डेटा", src_synthetic: "नमूना डेटा", src_manual: "केयर टीम ने दर्ज किया", src_phone: "फ़ोन ऐप", src_none: "कोई डिवाइस जुड़ा नहीं",
    synced: "सिंक", nothingYet: "पिछले 14 दिनों में कोई कॉल, अलर्ट या फ़ॉलो-अप नहीं।",
    callWord: "चेक-इन कॉल", mood_good: "अच्छे मूड में", mood_okay: "ठीक", mood_low: "उदास", mood_distressed: "परेशान", concernsW: "आगे देखना है", encouragedW: "साथी ने सुझाया", alertWord: "आपातकालीन अलर्ट", followWord: "फ़ॉलो-अप", transcript: "बातचीत देखें",
    st_completed: "पूरा", st_missed: "जवाब नहीं", st_declined: "मना किया", st_connected: "चल रही है", st_ringing: "घंटी बज रही है", st_initiated: "शुरू",
    st_active: "खुला", st_confirmed: "पुष्ट", st_false_alarm: "झूठा अलार्म", st_cancelled_by_senior: "उन्होंने रद्द किया", st_resolved: "सुलझा",
    cuesNone: "कोई लक्षण नहीं बताया",
    sosBar: "आपातकालीन अलर्ट", confirm: "आपातकाल की पुष्टि करें", falseAlarm: "झूठा अलार्म", resolvedT: "अलर्ट अपडेट हुआ",
    src_fall_need_help: "गिरना पकड़ा गया, मदद माँगी", src_fall_no_response: "गिरना पकड़ा गया, 30 सेकंड तक जवाब नहीं", src_senior_hold: "उनके फ़ोन का SOS बटन", src_voice_note: "आवाज़ के संदेश में बताया", src_call: "साथी कॉल पर बताया", src_missed_call: "हेल्प नंबर पर मिस्ड कॉल (साधारण फ़ोन)",
    schedTitle: "रोज़ की चेक-इन कॉल", schedNone: "अभी कोई रोज़ की कॉल तय नहीं। साथी हर दिन एक ही समय पर फ़ोन कर सकती है।", schedAdd: "समय जोड़ें", schedEvery: "हर दिन {t} बजे", schedRemove: "{t} हटाएं", schedSaved: "रोज़ की कॉल {t} बजे तय", schedRemoved: "रोज़ की कॉल हटाई गई", schedLast: "आख़िरी कॉल {w}",
    calling: "कॉल कर रहे हैं", ringingT: "उनके फ़ोन पर घंटी बज रही है…", connected: "जुड़ गए। साथी उनसे बात कर रहा है।",
    declined: "उन्होंने कॉल काट दी", missed: "जवाब नहीं मिला", completedT: "चेक-इन पूरा", offline: "उनका फ़ोन ऑफ़लाइन है, इसलिए कॉल नहीं जा सकी। बाद में फिर कोशिश करें या सीधे फ़ोन करें।",
    cues: "बताए गए लक्षण", meds: "दवा", taken: "ली", skipped: "नहीं ली", unknown: "पुष्टि नहीं", escalated: "आपके फ़ॉलो-अप के लिए चिह्नित", close: "बंद करें", done: "हो गया",
    followTitle: "फ़ॉलो-अप दर्ज करें", action: "आपने क्या किया?", outcome: "आपको क्या मिला?", useful: "क्या यह अलर्ट काम का था?",
    useYes: "काम का", useNo: "काम का नहीं", useRoutine: "रूटीन", notes: "टिप्पणी", notesHelp: "वैकल्पिक। आपकी टीम देख सकती है।", save: "फ़ॉलो-अप सेव करें", cancel: "रद्द करें",
    thanks: "फ़ॉलो-अप सेव हुआ। साथी इससे अलर्ट का क्रम बेहतर करेगा।",
    act_call_completed: "फ़ोन किया", act_nurse_dispatched: "नर्स / विज़िट भेजी", act_med_reviewed: "दवाओं की जाँच की",
    out_no_issue: "कोई समस्या नहीं", out_issue_confirmed: "समस्या पुष्ट हुई", out_escalated: "आगे भेजा",
    fb_useful: "काम का", fb_not_useful: "काम का नहीं", fb_routine: "रूटीन",
    allPeople: "सभी लोग", peopleSub: "आपको सौंपे गए सभी लोग, सबसे ज़रूरी पहले।",
    colName: "नाम", colStatus: "स्थिति", colCity: "शहर", colAge: "उम्र", colReason: "मुख्य कारण",
    opsSub: "सभी कोऑर्डिनेटर और शहरों में", monitored: "निगरानी में लोग", needToday: "आज ध्यान चाहिए", openAlerts: "खुले आपातकालीन अलर्ट",
    avgResp: "आपातकाल में औसत जवाब", followRate: "अलर्ट पर फ़ॉलो-अप", minutes: "मिनट",
    workload: "कोऑर्डिनेटर के अनुसार काम", byCity: "शहर के अनुसार", total: "कुल",
    emergencies: "आपातकालीन अलर्ट", falls: "गिरने की पहचान", calls: "चेक-इन कॉल", followUps: "फ़ॉलो-अप", learning: "राय से सीखना",
    totalAlerts: "कुल", confirmedN: "पुष्ट", falseN: "झूठे अलार्म", cancelledN: "उन्होंने रद्द किए",
    fTriggers: "कितनी बार चला", fOk: "वे ठीक थे", fFellOk: "गिरे पर ठीक", fHelp: "मदद माँगी", fNoAns: "जवाब नहीं",
    cEsc: "फ़ॉलो-अप के लिए चिह्नित", ratings: "कोऑर्डिनेटरों की रेटिंग", noRatings: "अभी कोई रेटिंग नहीं। फ़ॉलो-अप की रेटिंग तय करती हैं कि कौन-से कारण ज़्यादा गिने जाएँ।",
    accSub: "साथी बिगड़ती सेहत वाले लोगों को कितनी अच्छी तरह और कितनी जल्दी पहचानता है",
    catchRate: "गिरावट पकड़ी गई", precisionK: "सही निकले अलर्ट", earlyDays: "पहले से चेतावनी", falsePerWk: "झूठे अलर्ट",
    daysEarly: "दिन पहले, गंभीर होने से (मध्यिका)", perCoordWk: "प्रति कोऑर्डिनेटर प्रति सप्ताह", ofCases: "{n} गिरावट मामलों में से",
    compare: "हर हिस्से का योगदान", rulesOnly: "निजी बेसलाइन नियम", modelOnly: "पैटर्न मॉडल", combined: "साथी (संयुक्त)",
    langTitle: "लोगों की बात समझना", langSub: "हिंदी, हिंग्लिश और अंग्रेज़ी वाक्यों में लक्षण पहचान",
    trainedOn: "मॉडल का प्रशिक्षण", personDays: "व्यक्ति-दिन की रीडिंग", coverage: "उपयोगी घड़ी डेटा", coverageSub: "दिनों में स्कोर के लिए पर्याप्त रीडिंग",
    method: "पद्धति और सीमाएँ", threshold: "अलर्ट सीमा: प्राथमिकता {n} या उससे ज़्यादा।",
    when: "कब", who: "कौन", did: "क्या किया", target: "रिकॉर्ड", auditSub: "किसी व्यक्ति के रिकॉर्ड को देखने या बदलने का हर लॉग", roleStaff: "कोऑर्डिनेटर", roleOps: "ऑपरेशन्स", roleFamily: "परिवार",
    loadFail: "यह पेज लोड नहीं हुआ", loadFailSub: "कनेक्शन जाँचें। हम फिर कोशिश करते रहेंगे।", retry: "फिर कोशिश करें",
    summaryLine: "{a} को आज आपकी ज़रूरत है", summaryUrgent: "{n} अत्यावश्यक", summaryNone: "अभी किसी को कॉल की ज़रूरत नहीं",
  },
};
let lang = localStorage.getItem("aegis_lang") || "en";
const t = (k, vars) => { let s = (T[lang] && T[lang][k]) || T.en[k] || k; if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, b); return s; };
const has = (k) => !!(T.en[k]);
const L = (en, hi) => (lang === "hi" && hi ? hi : en);
const locale = () => (lang === "hi" ? "hi-IN" : "en-IN");

// ------------------------------------------------------------------------------------------ helpers
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ICONS = {
  logo: '<path d="M12,2.8l8,3.1v6c0,4.9 -3.4,8.5 -8,10.3C7.4,20.4 4,16.8 4,11.9v-6z"/><path d="M7.8,12.4h2.2l1.3,-2.6 2,5 1.3,-2.4h1.6"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16,16l4.5,4.5"/>',
  heart: '<path d="M12,19.6C5.5,14.3 3.2,11.5 3.2,8.5A4.6,4.6 0 0 1 12,6.7A4.6,4.6 0 0 1 20.8,8.5C20.8,11.5 18.5,14.3 12,19.6z"/>',
  steps: '<path d="M8.2,3.5C9.9,3.5 10.8,5.3 10.5,7.4 10.2,9.5 9.2,10.5 8,10.5 6.8,10.5 6,9.4 6,7.6 6,5.2 6.8,3.5 8.2,3.5z"/><path d="M16.2,9.5C17.9,9.5 18.8,11.3 18.5,13.4 18.2,15.5 17.2,16.5 16,16.5 14.8,16.5 14,15.4 14,13.6 14,11.2 14.8,9.5 16.2,9.5z"/>',
  drop: '<path d="M12,3.2C12,3.2 5.8,10 5.8,14.4A6.2,6.2 0 0 0 18.2,14.4C18.2,10 12,3.2 12,3.2z"/>',
  gauge: '<path d="M4,16a8,8 0 1 1 16,0"/><path d="M12,16l3.5,-4.5"/>',
  sugar: '<path d="M12,3.5l6,3.4v6.8L12,20.5 6,13.7V6.9z"/><path d="M12,9v5"/>',
  weight: '<path d="M5,8h14l1.5,11h-17z"/><path d="M9,8a3,3 0 0 1 6,0"/>',
  moon: '<path d="M19,14.5A7.5,7.5 0 1 1 9.5,5 6,6 0 0 0 19,14.5z"/>',
  phone: '<path d="M6.2,3.8h3l1.5,3.9-1.9,1.4a11,11 0 0 0 4.1,4.1l1.4,-1.9 3.9,1.5v3A2.2,2.2 0 0 1 15.9,19.9C9.2,19.3 4.7,14.8 4.1,8.1A2.2,2.2 0 0 1 6.2,3.8z"/>',
  warn: '<path d="M12,3.6L21,19.4H3z"/><path d="M12,9.8v4.4"/><path d="M12,17h.01"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12,7.5v5"/><path d="M12,16h.01"/>',
  eye: '<path d="M2.5,12C4.5,7.8 8,5.5 12,5.5S19.5,7.8 21.5,12C19.5,16.2 16,18.5 12,18.5S4.5,16.2 2.5,12z"/><circle cx="12" cy="12" r="3"/>',
  check: '<path d="M5.2,12.6l4.4,4.4L18.8,7.6"/>', checkCircle: '<circle cx="12" cy="12" r="9"/><path d="M8,12.4l2.8,2.8L16.2,9.6"/>',
  close: '<path d="M6.4,6.4l11.2,11.2"/><path d="M17.6,6.4L6.4,17.6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12,7.4V12l3.2,1.9"/>',
  user: '<circle cx="12" cy="7.5" r="3.8"/><path d="M4.6,20.4C5.2,16.8 8.2,14.8 12,14.8S18.8,16.8 19.4,20.4"/>',
  pin: '<path d="M12,21s-6.5-5.6-6.5-11a6.5,6.5 0 0 1 13,0c0,5.4-6.5,11-6.5,11z"/><circle cx="12" cy="10" r="2.4"/>',
  plus: '<path d="M12,5v14M5,12h14"/>',
  users: '<circle cx="9" cy="8" r="3.4"/><path d="M2.8,19.5C3.4,16.3 5.9,14.5 9,14.5S14.6,16.3 15.2,19.5"/><path d="M15.5,4.9a3.4,3.4 0 0 1 0,6.2"/><path d="M17.5,14.8c2,.6 3.4,2.2 3.8,4.7"/>',
  home: '<path d="M4,10.5L12,4l8,6.5V20H4z"/><path d="M9.5,20v-5.5h5V20"/>',
  chart: '<path d="M4,20V4"/><path d="M4,20h16"/><path d="M8,16v-5"/><path d="M12.5,16V8"/><path d="M17,16v-3"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
  list: '<path d="M8.5,6.5h11"/><path d="M8.5,12h11"/><path d="M8.5,17.5h11"/><path d="M4.5,6.5h.01"/><path d="M4.5,12h.01"/><path d="M4.5,17.5h.01"/>',
  chevR: '<path d="M9.5,5.5L16,12l-6.5,6.5"/>', chevL: '<path d="M14.5,5.5L8,12l6.5,6.5"/>',
  logout: '<path d="M14,4.5H18.5V19.5H14"/><path d="M10,8l-4,4 4,4"/><path d="M6,12h9"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12,11v5.5"/><path d="M12,7.8h.01"/>',
  bulb: '<path d="M9,17.5h6"/><path d="M10,20.5h4"/><path d="M12,3.5a6,6 0 0 0 -3.6,10.8c.7,.6 1.1,1.4 1.1,2.2h5c0,-.8 .4,-1.6 1.1,-2.2A6,6 0 0 0 12,3.5z"/>',
  pill: '<g transform="rotate(-45 12 12)"><path d="M8,8.2H16A3.8,3.8 0 0 1 16,15.8H8A3.8,3.8 0 0 1 8,8.2z"/><path d="M12,8.2V15.8"/></g>',
  watch: '<path d="M8.4,6.2h7.2a2,2 0 0 1 2,2v7.6a2,2 0 0 1 -2,2H8.4a2,2 0 0 1 -2,-2V8.2a2,2 0 0 1 2,-2z"/><path d="M9.2,6.2L9.8,3h4.4l.6,3.2"/><path d="M9.2,17.8L9.8,21h4.4l.6,-3.2"/>',
  shield: '<path d="M12,3l7.2,2.8v5.6c0,4.6 -3.1,8 -7.2,9.6C7.9,19.4 4.8,16 4.8,11.4V5.8z"/><path d="M8.8,12l2.4,2.4L15.6,9.6"/>',
  mic: '<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5,11.5a6.5,6.5 0 0 0 13,0"/><path d="M12,18v2.5"/>',
  fall: '<circle cx="15" cy="5.5" r="2"/><path d="M13.5,9L9,12.5l3,3-1.5,5"/><path d="M9,12.5L5,11"/><path d="M15,10.5l3,3"/><path d="M4,20.5h16"/>',
  refresh: '<path d="M19.5,12a7.5,7.5 0 1 1 -2.2,-5.3"/><path d="M19.5,4.5v4h-4"/>',
};
const ico = (n, cls = "") => `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;
const fmt = (n, d = 0) => (n === null || n === undefined || Number.isNaN(Number(n)) ? "–" : Number(n).toLocaleString(locale(), { maximumFractionDigits: d, minimumFractionDigits: d }));
const titleCase = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());
const initials = (n) => String(n || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

function parseTime(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return new Date(v < 1e12 ? v * 1000 : v);
  const d = new Date(String(v).replace(" ", "T"));
  return isNaN(d) ? null : d;
}
function rel(v) {
  const d = parseTime(v); if (!d) return v ? String(v) : "";
  const sec = Math.round((d - Date.now()) / 1000), a = Math.abs(sec);
  const rtf = new Intl.RelativeTimeFormat(locale(), { numeric: "auto" });
  if (a < 45) return t("justNow");
  if (a < 3600) return rtf.format(Math.round(sec / 60), "minute");
  if (a < 86400) return rtf.format(Math.round(sec / 3600), "hour");
  if (a < 7 * 86400) return rtf.format(Math.round(sec / 86400), "day");
  return d.toLocaleDateString(locale(), { day: "numeric", month: "short" });
}
function ageRel(sec) { return sec === null || sec === undefined ? "" : rel(Date.now() - sec * 1000); }
const fullTime = (v) => { const d = parseTime(v); return d ? d.toLocaleString(locale(), { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : String(v || ""); };

const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
function animateNums(scope) {
  // KPI figures count up from zero on a view's first paint; anything not a bare number is left alone
  if (REDUCED) return;
  scope.querySelectorAll(".kpi .v, .big-n, .prio b").forEach((el) => {
    const raw = el.textContent.trim();
    const m = raw.match(/^([+-]?\d[\d,]*(?:\.\d+)?)(%)?$/);
    if (!m) return;
    const target = parseFloat(m[1].replace(/,/g, ""));
    if (!isFinite(target) || target === 0) return;
    const dec = (m[1].split(".")[1] || "").length, suffix = m[2] || "";
    const t0 = performance.now(), dur = 650;
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * e).toLocaleString(locale(), { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suffix;
      if (p < 1) requestAnimationFrame(step); else el.textContent = raw;
    };
    requestAnimationFrame(step);
  });
}

let toastBox = null;
function toast(m, kind = "") {
  if (!toastBox) { toastBox = document.createElement("div"); toastBox.className = "toasts"; toastBox.setAttribute("role", "status"); toastBox.setAttribute("aria-live", "polite"); document.body.appendChild(toastBox); }
  const d = document.createElement("div"); d.className = `toast ${kind}`; d.innerHTML = `${ico(kind === "err" ? "alert" : "checkCircle")}<span>${esc(m)}</span>`;
  toastBox.appendChild(d); setTimeout(() => d.remove(), kind === "err" ? 5000 : 3200);
}

// tier vocabulary: colour is always paired with an icon and a word
const TIER = { RED: { k: "urgent", c: "crit", i: "warn" }, ORANGE: { k: "attention", c: "high", i: "alert" }, YELLOW: { k: "watch", c: "watch", i: "eye" }, GREEN: { k: "stable", c: "ok", i: "checkCircle" } };
const TIERS = ["RED", "ORANGE", "YELLOW", "GREEN"];
// risk tiers as chart colours (validated for colour-blind separation; always shown with a label)
const VIZ = { RED: "var(--viz-crit)", ORANGE: "var(--viz-high)", YELLOW: "var(--viz-watch)", GREEN: "var(--viz-ok)" };
const tierParts = (r) => TIERS.map((k) => ({ label: t(TIER[k].k), value: r[k] || 0, color: VIZ[k] }));
const tierLegend = (r) => Charts.legend(TIERS.map((k) => ({ label: t(TIER[k].k), value: r[k] || 0, color: VIZ[k] })));
const dayLabel = (iso) => { const d = new Date(iso + "T12:00:00"); return d.toLocaleDateString(locale(), { day: "numeric", month: "short" }); };
const daysBack = (n) => Array.from({ length: n }, (_, i) => new Date(Date.now() - (n - 1 - i) * 86400000).toISOString().slice(0, 10));
function vizDone(root) { window.__vizTableLabel = L("Table", "तालिका"); Charts.bind(root || document); }

/* Leaflet (OpenStreetMap) is loaded only when a real location has to be shown, and only if the browser is
   online; otherwise the card keeps the coordinates and a link that opens them in a maps app. */
let leafletReady = null;
function loadLeaflet() {
  if (window.L && window.L.map) return Promise.resolve(window.L);
  if (leafletReady) return leafletReady;
  leafletReady = new Promise((ok, no) => {
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"; document.head.appendChild(css);
    const js = document.createElement("script"); js.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    js.onload = () => ok(window.L); js.onerror = () => { leafletReady = null; no(new Error("offline")); }; document.head.appendChild(js);
  });
  return leafletReady;
}
async function streetMap(el, pins) {
  if (!el || !pins.length || el.__map) return;
  try {
    const Lf = await loadLeaflet();
    const m = Lf.map(el, { scrollWheelZoom: false, attributionControl: true });
    Lf.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(m);
    const pts = pins.map((p) => { Lf.circleMarker([p.lat, p.lon], { radius: 9, color: "#fff", weight: 2, fillColor: "#c8362c", fillOpacity: 1 }).addTo(m).bindTooltip(p.label); return [p.lat, p.lon]; });
    if (pts.length === 1) m.setView(pts[0], 15); else m.fitBounds(pts, { padding: [30, 30] });
    el.__map = m; el.classList.add("ready");
  } catch (e) { el.classList.add("offline"); }
}
const gmaps = (lat, lon) => `https://www.google.com/maps?q=${Number(lat).toFixed(6)},${Number(lon).toFixed(6)}`;

const badge = (tier) => { const x = TIER[tier] || TIER.GREEN; return `<span class="badge ${x.c}">${ico(x.i)}${t(x.k)}</span>`; };

/* Sparkline that copes with sparse metrics (BP, sugar, weight are not daily): it joins the readings that
   exist and marks each with a dot, instead of lifting the pen at every gap. */
function spark(values) {
  const pts = (values || []).map((x, i) => [i, x === null || x === undefined ? null : Number(x)]).filter((p) => p[1] !== null && !Number.isNaN(p[1]));
  if (pts.length < 2) return "";
  const n = Math.max(values.length - 1, 1), ys = pts.map((p) => p[1]);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const xy = pts.map(([i, y]) => [(i / n) * 100, 28 - ((y - lo) / span) * 24]);
  const d = xy.map((p, k) => `${k ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const sparse = pts.length < values.length * 0.7;
  const dots = (sparse ? xy : [xy[xy.length - 1]]).map((p) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.6" fill="var(--brand)" vector-effect="non-scaling-stroke"/>`).join("");
  return `<svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" d="${d}" fill="none" stroke="var(--brand)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>${dots}</svg>`;
}

// ------------------------------------------------------------------------------------------ state + api
const S = {
  token: sessionStorage.getItem("aegis_token"), role: sessionStorage.getItem("aegis_role"), code: sessionStorage.getItem("aegis_code"), name: sessionStorage.getItem("aegis_name"),
  route: { view: "", id: null }, filter: "ALL", search: "", showStable: false,
  queue: null, summary: null, sos: [], selected: null, detail: null, detailHash: "", listHash: "",
  ops: null, metrics: null, audit: null, error: null, lastSync: null, demoMode: false,
  animated: {},   // views already given their entrance animation (data refreshes never replay it)
};

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(S.token ? { Authorization: "Bearer " + S.token } : {}), ...(opts.headers || {}) } });
  if (r.status === 401 && S.token) { logout(); throw new Error("Signed out"); }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(body.detail || `Error ${r.status}`); e.status = r.status; throw e; }
  return body;
}
function logout() { sessionStorage.clear(); Object.assign(S, { token: null, role: null, queue: null, detail: null, ops: null, metrics: null, audit: null }); stopPolling(); history.replaceState(null, "", location.pathname); renderLogin(); }

// ------------------------------------------------------------------------------------------ sign-in
async function renderLogin() {
  document.title = `${t("signInTitle")} · ${t("appName")}`;
  const app = $("#app");
  let samples = null;
  try { const h = await fetch("/api/health").then((r) => r.json()); S.demoMode = !!h.demo_mode; if (S.demoMode) samples = await fetch("/api/auth/demo").then((r) => (r.ok ? r.json() : null)); } catch (e) {}
  app.innerHTML = `<div class="auth">
    <section class="story" aria-hidden="false">
      <div class="brand"><div class="mark">${ico("logo")}</div><span>${t("appName")}<small>${t("tagline")}</small></span></div>
      <img class="story-ill" src="/static/illustrations/desk.svg" alt="" width="360" height="300" decoding="async">
      <div><h2>${t("storyTitle")}</h2><p>${t("storyText")}</p></div>
      <ul class="points"><li>${ico("list")}${t("p1")}</li><li>${ico("mic")}${t("p2")}</li><li>${ico("shield")}${t("p3")}</li></ul>
    </section>
    <main class="form-side"><form class="form" id="lf" novalidate>
      <div class="row" style="justify-content:flex-end;margin-bottom:var(--s5)">${langSeg()}</div>
      <h1>${t("signInTitle")}</h1><p>${t("signInSub")}</p>
      <div class="field"><span class="label" id="roleL">${t("role")}</span><div class="seg full" id="roleSeg" role="group" aria-labelledby="roleL">
        <button type="button" data-r="coordinator" aria-pressed="true">${t("coordinator")}</button><button type="button" data-r="ops" aria-pressed="false">${t("operations")}</button></div></div>
      <label class="field"><span class="label">${t("code")}</span><input class="input" id="lcode" name="username" autocomplete="username" autocapitalize="characters" spellcheck="false" placeholder="SAM-101" required></label>
      <label class="field"><span class="label">${t("pin")}</span><span class="input-wrap"><input class="input" id="lpin" name="password" type="password" inputmode="numeric" autocomplete="current-password" required>
        <button type="button" class="btn quiet icon" id="pinEye" aria-label="${t("showPin")}" aria-pressed="false">${ico("eye")}</button></span></label>
      <div class="field"><div class="error hidden" id="lerr" role="alert"></div></div>
      <button class="btn primary lg block" id="lgo" type="submit" style="margin-top:var(--s4)">${t("go")}</button>
      ${samples ? `<details class="samples"><summary>${t("samples")}</summary><div class="list-s">${samples.coordinators.map((c) => `<button type="button" data-c="${esc(c.code)}" data-p="${esc(c.pin)}" data-r="coordinator">${esc(c.name)} · ${esc(c.code)}</button>`).join("")}${samples.ops.map((o) => `<button type="button" data-c="${esc(o.code)}" data-p="${esc(o.pin)}" data-r="ops">${t("operations")} · ${esc(o.code)}</button>`).join("")}</div></details>` : ""}
      <p class="alt">${t("familyQ")} <a href="/family">${t("familyLink")}</a></p>
    </form></main></div>`;
  let role = "coordinator";
  const setRole = (r) => { role = r; $("#roleSeg").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.r === r)); $("#lcode").placeholder = r === "ops" ? "OPS-1" : "SAM-101"; };
  $("#roleSeg").onclick = (e) => { const b = e.target.closest("button"); if (b) setRole(b.dataset.r); };
  $("#pinEye").onclick = () => { const p = $("#lpin"), show = p.type === "password"; p.type = show ? "text" : "password"; $("#pinEye").setAttribute("aria-pressed", show); $("#pinEye").setAttribute("aria-label", show ? t("hidePin") : t("showPin")); };
  app.querySelectorAll("details.samples button").forEach((b) => (b.onclick = () => { setRole(b.dataset.r); $("#lcode").value = b.dataset.c; $("#lpin").value = b.dataset.p; $("#lgo").focus(); }));
  bindLang(app, renderLogin);
  const err = (m) => { const e = $("#lerr"); e.innerHTML = `${ico("alert", "s")}<span>${esc(m)}</span>`; e.classList.remove("hidden"); $("#lcode").setAttribute("aria-invalid", "true"); $("#lpin").setAttribute("aria-invalid", "true"); };
  $("#lf").onsubmit = async (ev) => {
    ev.preventDefault();
    const code = $("#lcode").value.trim(), pin = $("#lpin").value.trim();
    if (!code || !pin) return err(t("needBoth"));
    const b = $("#lgo"); b.setAttribute("aria-busy", "true"); b.innerHTML = `<span class="spin"></span>${t("signingIn")}`;
    try {
      const r = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ role, id: code, secret: pin }) });
      Object.assign(S, { token: r.token, role: r.role, code: r.code, name: r.name });
      sessionStorage.setItem("aegis_token", r.token); sessionStorage.setItem("aegis_role", r.role); sessionStorage.setItem("aegis_code", r.code); sessionStorage.setItem("aegis_name", r.name || "");
      location.hash = r.role === "ops" ? "#/overview" : "#/today"; start();
    } catch (e) { b.removeAttribute("aria-busy"); b.textContent = t("go"); err(e.status === 401 ? t("wrong") : e.message); }
  };
}
const langSeg = () => `<div class="seg" role="group" aria-label="${t("language")}" data-lang><button type="button" data-l="hi" aria-pressed="${lang === "hi"}" lang="hi">हिंदी</button><button type="button" data-l="en" aria-pressed="${lang === "en"}" lang="en">English</button></div>`;
function bindLang(root, rerender) {
  root.querySelectorAll("[data-lang]").forEach((s) => (s.onclick = (e) => { const b = e.target.closest("button"); if (b && b.dataset.l !== lang) { lang = b.dataset.l; localStorage.setItem("aegis_lang", lang); document.documentElement.lang = lang; rerender(); } }));
}

// ------------------------------------------------------------------------------------------ routing + shell
const NAV = {
  coordinator: [["today", "home", "today"], ["people", "users", "people"], ["accuracy", "target", "accuracy"]],
  ops: [["overview", "chart", "overview"], ["accuracy", "target", "accuracy"], ["audit", "list", "audit"]],
};
function parseRoute() {
  const p = location.hash.replace(/^#\/?/, "").split("/");
  const views = NAV[S.role].map((n) => n[0]);
  return { view: views.includes(p[0]) ? p[0] : views[0], id: p[1] ? decodeURIComponent(p[1]) : null };
}
let timer = null;
function stopPolling() { clearInterval(timer); timer = null; }
function start() {
  S.route = parseRoute(); renderShell(); load();
  stopPolling(); timer = setInterval(() => { if (!document.hidden) load(true); }, 8000);
}
window.addEventListener("hashchange", () => {
  if (!S.token) return;
  const prev = S.route; S.route = parseRoute();
  if (prev.view !== S.route.view) { S.error = null; renderShell(); load(); window.scrollTo(0, 0); return; }
  if (S.route.id && S.route.id !== S.selected) { S.selected = S.route.id; S.detail = null; S.detailHash = ""; loadDetail(); }
  draw(); if (S.route.id && matchMedia("(max-width: 860px)").matches) window.scrollTo(0, 0);
});

function renderShell() {
  S.animated = {};
  const nav = NAV[S.role], v = S.route.view;
  const titles = { today: t("today"), people: t("allPeople"), overview: t("overview"), accuracy: t("accuracy"), audit: t("audit") };
  const subs = { today: new Date().toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" }), people: t("peopleSub"), overview: t("opsSub"), accuracy: t("accSub"), audit: t("auditSub") };
  document.title = `${titles[v]} · ${t("appName")}`;
  const sosCount = S.sos.length ? `<span class="count num" aria-label="${S.sos.length} ${t("sosBar")}">${S.sos.length}</span>` : "";
  const links = (cls) => nav.map(([k, i, label]) => `<a href="#/${k}" ${k === v ? 'aria-current="page"' : ""} class="${cls}">${ico(i)}<span>${t(label)}</span>${k === "today" ? sosCount : ""}</a>`).join("");
  const searchable = v === "today" || v === "people";
  setTimeout(() => { const k = $("#skip"); if (k) k.onclick = (e) => { e.preventDefault(); $("#page").focus(); }; });
  $("#app").innerHTML = `<a class="skip" href="#" id="skip">${L("Skip to content", "सामग्री पर जाएँ")}</a><div class="shell">
    <aside class="side" aria-label="${t("appName")}">
      <a class="brand" href="#/${nav[0][0]}"><div class="mark">${ico("logo")}</div><span>${t("appName")}<small>${t("tagline")}</small></span></a>
      <nav class="nav" aria-label="Main">${links("")}</nav>
      <div class="foot">${langSeg()}
        <div class="acct"><div class="avatar" aria-hidden="true">${esc(initials(S.name || S.code))}</div><div class="who"><b>${esc(S.name || S.code)}</b><span>${S.role === "ops" ? t("operations") : t("coordinator")} · ${esc(S.code)}</span></div></div>
        <button class="btn quiet block" id="out" style="justify-content:flex-start">${ico("logout")}<span>${t("signOut")}</span></button></div>
    </aside>
    <div class="main">
      <header class="top">
        <a class="brand mobile-brand" href="#/${nav[0][0]}" aria-label="${t("appName")}"><div class="mark">${ico("logo")}</div></a>
        <div class="title grow"><h1>${titles[v]}</h1><p>${esc(subs[v])}</p></div>
        ${searchable ? `<div class="search" id="searchBox" role="search">${ico("search", "s")}<input class="input" id="q" type="search" placeholder="${t("search")}" aria-label="${t("search")}" value="${esc(S.search)}" autocomplete="off"></div>
          <button class="btn quiet icon mob-only" id="searchBtn" aria-label="${t("openSearch")}">${ico("search")}</button>` : ""}
        <button class="btn quiet icon mob-only" id="acctBtn" aria-label="${t("account")}"><span class="avatar" style="width:32px;height:32px">${esc(initials(S.name || S.code))}</span></button>
      </header>
      <div id="sos"></div>
      <main class="page" id="page" tabindex="-1"></main>
    </div></div>
    <nav class="bottom-nav" aria-label="Main">${links("")}</nav>`;
  $("#out").onclick = logout;
  bindLang($(".side"), () => { renderShell(); });
  const q = $("#q"); if (q) q.oninput = () => { S.search = q.value; draw(); };
  const sb = $("#searchBtn"); if (sb) sb.onclick = () => { $("#searchBox").classList.add("open"); q.focus(); };
  if (q) q.onblur = () => { if (!q.value) $("#searchBox").classList.remove("open"); };
  const ab = $("#acctBtn"); if (ab) ab.onclick = accountSheet;
  drawSosBar(); draw();
}
function accountSheet() {
  const d = dialog(`<div class="dlg-h"><div class="avatar">${esc(initials(S.name || S.code))}</div><div class="grow"><h3>${esc(S.name || S.code)}</h3><p class="sm subtle">${S.role === "ops" ? t("operations") : t("coordinator")} · ${esc(S.code)}</p></div>
    <button class="btn quiet icon" data-close aria-label="${t("close")}">${ico("close")}</button></div>
    <div class="dlg-b stack"><div class="field"><span class="label">${t("language")}</span>${langSeg()}</div>
    <button class="btn secondary block" id="out2">${ico("logout")}${t("signOut")}</button></div>`, t("account"));
  bindLang(d.el, () => { d.close(); renderShell(); });
  $("#out2", d.el).onclick = () => { d.close(); logout(); };
}

// ------------------------------------------------------------------------------------------ data loading
async function load(silent) {
  try {
    const v = S.route.view;
    if (S.role === "coordinator") {
      const [q, sos] = await Promise.all([api(`/api/coordinator/${S.code}/seniors`), api(`/api/coordinator/${S.code}/sos`)]);
      const h = JSON.stringify([q.seniors.map((s) => [s.senior_id, s.risk_score, s.tier, s.sos.active, (s.why_today_en || [])[0]]), q.summary]);
      const sosChanged = JSON.stringify(sos.map((x) => x.id)) !== JSON.stringify(S.sos.map((x) => x.id));
      S.queue = q.seniors; S.summary = q.summary; S.sos = sos;
      if (v === "accuracy" && !S.metrics) S.metrics = await api("/api/ops/metrics");
      if (sosChanged) { drawSosBar(); updateCounts(); }
      if (v === "today") {
        const want = S.route.id || (S.selected && S.queue.some((x) => x.senior_id === S.selected) ? S.selected : (S.queue[0] || {}).senior_id);
        if (want !== S.selected) { S.selected = want; S.detail = null; S.detailHash = ""; }
      }
      // draw the list first; the record's history loads after it so the page is usable at once
      if (h !== S.listHash || !silent || S.error) { S.listHash = h; S.error = null; draw(); }
      else updateSync();
      if (v === "today" && S.selected) loadDetail(true);
    } else {
      if (v === "overview") S.ops = await api("/api/ops/overview");
      else if (v === "accuracy") S.metrics = await api("/api/ops/metrics");
      else S.audit = await api("/api/ops/audit?limit=200");
      S.error = null; draw();
    }
    S.lastSync = Date.now(); updateSync();
  } catch (e) { if (e.message === "Signed out") return; if (!silent || !hasData()) { S.error = e.message; draw(); } }
}
const hasData = () => (S.role === "coordinator" ? !!S.queue : !!(S.ops || S.metrics || S.audit));
async function loadDetail(silent) {
  if (!S.selected) return;
  try {
    const [d, sched] = await Promise.all([api(`/api/senior/${encodeURIComponent(S.selected)}/details`),
      api(`/api/calls/schedule/${encodeURIComponent(S.selected)}`).catch(() => [])]);
    d.schedules = sched;
    const h = JSON.stringify([d.calls, d.sos, d.actions, d.timeline_14d, d.schedules, d.medicines, d.contacts, d.senior, d.speech]);
    S.detail = d; if (h !== S.detailHash) { S.detailHash = h; drawDetail(); }
  } catch (e) { if (!silent) toast(e.message, "err"); }
}
function updateSync() { const el = $("#syncTxt"); if (el && S.lastSync) el.textContent = `${t("updated")} ${rel(S.lastSync)}`; }
function updateCounts() { if (S.token && $("#app .shell")) document.querySelectorAll('.nav a[href="#/today"], .bottom-nav a[href="#/today"]').forEach((a) => { const c = a.querySelector(".count"); if (c) c.remove(); if (S.sos.length) a.insertAdjacentHTML("beforeend", `<span class="count num">${S.sos.length}</span>`); }); }

function draw() {
  const page = $("#page"); if (!page) return;
  try {
    if (S.error && !hasData()) { page.innerHTML = errorState(); $("#retry").onclick = () => load(); return; }
    const v = S.route.view;
    const loading = (v === "today" || v === "people") ? !S.queue : !hasData();
    const first = !S.animated[v];
    page.classList.toggle("enter", first && !loading);
    if (!loading) S.animated[v] = true;
    if (v === "today") drawToday(); else if (v === "people") drawPeople(); else if (v === "overview") drawOverview(); else if (v === "accuracy") drawAccuracy(); else drawAudit();
    if (first && !loading) animateNums(page);
    if (!loading) vizDone(page);
  } catch (e) { console.error(e); page.innerHTML = errorState(e.message); const r = $("#retry"); if (r) r.onclick = () => load(); }
}
const errorState = (detail) => `<div class="card"><div class="empty">${ico("alert", "xl")}<h3>${t("loadFail")}</h3><p>${t("loadFailSub")}</p>${detail ? `<p class="xs subtle" style="margin-top:8px">${esc(detail)}</p>` : ""}<button class="btn secondary" id="retry" style="margin-top:16px">${ico("refresh")}${t("retry")}</button></div></div>`;
const skeletonList = (n = 6) => Array.from({ length: n }, () => `<div style="padding:16px;border-bottom:1px solid var(--line)"><span class="skel" style="height:16px;width:45%"></span><span class="skel" style="height:12px;width:80%;margin-top:8px"></span></div>`).join("");

// ------------------------------------------------------------------------------------------ emergency bar
function drawSosBar() {
  const box = $("#sos"); if (!box) return;
  box.innerHTML = S.sos.map((e) => {
    const src = has("src_" + e.source) ? t("src_" + e.source) : (e.source || "");
    const said = e.said ? `<div class="sm">${L("Said", "कहा")}: “${esc(e.said)}”</div>` : "";
    const fam = (e.notify_log || []).map((r) => {
      const how = { ringing: L("ringing", "घंटी जा रही"), connected: L("told", "बता दिया"), no_answer: L("no answer", "नहीं उठाया"),
        busy: L("busy", "व्यस्त"), failed: L("could not call", "कॉल नहीं लगी"), no_report: L("no answer", "नहीं उठाया") }[r.status] || r.status;
      const ack = r.acknowledged ? ` (${esc(r.acknowledged)})` : "";
      return `${esc(r.name)} ${esc(r.time || "")}: ${esc(how)}${ack}`;
    }).join(" · ");
    const famLine = fam ? `<div class="sm">${L("Family alert call", "परिवार को कॉल")}: ${fam}</div>`
      : e.alert_state === "phone_fallback" || e.alert_state === "unreached" ? `<div class="sm">${L("Family alert: the phone is dialling the emergency contact", "परिवार: फ़ोन आपातकालीन संपर्क को कॉल कर रहा है")}</div>` : "";
    const creditLine = e.alert_state === "no_credit" ? `<div class="sm"><b>${L("Saathi could not call the family: the Sarvam account is out of credit. Please call them yourself.", "साथी परिवार को कॉल नहीं कर सका: Sarvam खाते में बैलेंस नहीं है। कृपया स्वयं कॉल करें।")}</b></div>` : "";
    return `<div class="sos-bar" role="alert">${ico("warn", "l")}<div class="what"><b>${t("sosBar")}: ${esc(e.senior_name)}</b><div class="sm">${esc(src)} · ${esc(rel(e.ts || e.time))}</div>${said}${famLine}${creditLine}</div>
      <div class="acts"><a class="btn secondary" href="#/today/${encodeURIComponent(e.senior_id || "")}">${L("Open record", "रिकॉर्ड खोलें")}</a>
      <button class="btn danger" data-s="confirmed" data-id="${esc(e.id)}">${t("confirm")}</button><button class="btn on-danger" data-s="false_alarm" data-id="${esc(e.id)}">${t("falseAlarm")}</button></div></div>`;
  }).join("");
  box.onclick = async (ev) => {
    const b = ev.target.closest("button[data-s]"); if (!b) return;
    b.setAttribute("aria-busy", "true");
    try { await api(`/api/sos/${b.dataset.id}/resolve`, { method: "POST", body: JSON.stringify({ status: b.dataset.s, coordinator_code: S.code }) }); toast(t("resolvedT")); S.sos = S.sos.filter((x) => String(x.id) !== b.dataset.id); drawSosBar(); updateCounts(); load(true); }
    catch (e) { b.removeAttribute("aria-busy"); toast(e.message, "err"); }
  };
}

// ------------------------------------------------------------------------------------------ coordinator: Today
function greeting() { const h = new Date().getHours(); return h < 12 ? t("morning") : h < 17 ? t("afternoon") : t("evening"); }
function matches(s) { const q = S.search.trim().toLowerCase(); return !q || s.name.toLowerCase().includes(q) || String(s.city || "").toLowerCase().includes(q); }

function drawToday() {
  const page = $("#page");
  if (!S.queue) { page.innerHTML = `<div class="split"><div class="card list">${skeletonList()}</div><div class="card"><div class="dh"><span class="skel" style="height:28px;width:40%"></span><span class="skel" style="height:14px;width:30%;margin-top:12px"></span></div></div></div>`; return; }
  const c = S.summary || {};
  const counts = { ALL: c.total_assigned || S.queue.length, RED: c.urgent_red || 0, ORANGE: c.attention_orange || 0, YELLOW: c.monitor_yellow || 0, GREEN: c.stable_green || 0 };
  const need = counts.RED + counts.ORANGE + counts.YELLOW;
  const firstName = String(S.name || "").split(" ")[0];
  const line = need ? `${t("summaryLine", { a: `<b>${need}</b> ${L(need === 1 ? "person" : "people", "लोगों")}` })}${counts.RED ? ` · <b style="color:var(--crit-ink)">${t("summaryUrgent", { n: counts.RED })}</b>` : ""}` : t("summaryNone");
  const chip = (k, label, dot) => `<button class="filter" data-f="${k}" aria-pressed="${S.filter === k}">${dot ? `<span class="dot ${dot}"></span>` : ""}${label}<span class="n">${counts[k]}</span></button>`;
  const hasDetail = !!S.route.id;
  const mix = { RED: counts.RED, ORANGE: counts.ORANGE, YELLOW: counts.YELLOW, GREEN: counts.GREEN };
  page.innerHTML = `<div class="today ${hasDetail ? "has-detail" : ""}"><section class="hero greet">
      <div class="hero-txt"><h2>${greeting()}${firstName ? `, ${esc(firstName)}` : ""}</h2><p>${line}</p>
        <span class="sync"><span class="dot live"></span><span id="syncTxt">${t("updated")} ${S.lastSync ? rel(S.lastSync) : t("justNow")}</span></span></div>
      <div class="hero-viz">${Charts.donut({ segments: tierParts(mix), size: 120, thick: 16, center: fmt(counts.ALL), centerSub: L("people", "लोग"),
        label: L("My caseload by priority", "प्राथमिकता के अनुसार मेरे लोग") + ": " + TIERS.map((k) => `${t(TIER[k].k)} ${mix[k]}`).join(", ") })}${tierLegend(mix)}</div></section>
    <div class="filters" role="group" aria-label="${t("colStatus")}">${chip("ALL", t("all"))}${chip("RED", t("urgent"), "crit")}${chip("ORANGE", t("attention"), "high")}${chip("YELLOW", t("watch"), "watch")}${chip("GREEN", t("stable"), "ok")}</div>
    <div class="split ${hasDetail ? "has-detail" : ""}">
      <section class="list-col" aria-label="${t("today")}"><div class="card list" id="qlist"></div></section>
      <section class="detail-col" aria-live="polite"><div class="back-row"><a class="link" href="#/today">${ico("chevL", "s")}${t("back")}</a></div><div class="card detail-pane" id="detail"></div></section>
    </div></div>`;
  page.querySelector(".filters").onclick = (e) => { const b = e.target.closest(".filter"); if (b) { S.filter = b.dataset.f; draw(); } };
  drawList(); drawDetail(); vizDone(page.querySelector(".hero"));
}
function personRow(s) {
  const x = TIER[s.tier] || TIER.GREEN, why = L((s.why_today_en || [])[0], (s.why_today_hi || [])[0]) || "";
  return `<a class="person ${x.c}" href="#/today/${encodeURIComponent(s.senior_id)}" ${S.selected === s.senior_id ? 'aria-current="true"' : ""}>
    <span class="rail" aria-hidden="true"></span>
    <span class="grow"><span class="nm"><span>${esc(s.name)}</span>${s.sos.active ? `<span class="badge crit">${ico("warn")}SOS</span>` : ""}</span><span class="why">${esc(why)}</span></span>
    <span class="row"><span class="meta">${esc(s.age)} · ${esc(titleCase(s.city))}<br><span class="sr-only">${t(x.k)}</span></span>${ico("chevR", "s chev")}</span></a>`;
}
function drawList() {
  const box = $("#qlist"); if (!box) return;
  const rows = S.queue.filter((s) => (S.filter === "ALL" || s.tier === S.filter) && matches(s));
  if (!rows.length) {
    const calm = S.filter !== "ALL" && S.filter !== "GREEN" && !S.search;
    box.innerHTML = `<div class="empty"><img class="empty-ill" src="/static/illustrations/${calm ? "all_done" : "search_empty"}.svg" alt="" width="360" height="300" decoding="async"><h3>${calm ? t("allCalm") : t("nobody")}</h3><p class="sm">${calm ? t("allCalmSub") : t("nobodySub")}</p>
      <button class="btn secondary" id="clr" style="margin-top:16px">${t("clearFilter")}</button></div>`;
    $("#clr").onclick = () => { S.filter = "ALL"; S.search = ""; const q = $("#q"); if (q) q.value = ""; draw(); };
    return;
  }
  let html = "";
  TIERS.forEach((k) => {
    const g = rows.filter((x) => x.tier === k); if (!g.length) return;
    const canFold = k === "GREEN" && S.filter === "ALL" && !S.search.trim();
    const folded = canFold && !S.showStable;
    html += `<div class="grp-h"><span class="dot ${TIER[k].c}"></span>${t(TIER[k].k)}<span class="n num">${g.length}</span>${canFold ? `<button class="link" id="fold" aria-expanded="${!folded}">${folded ? t("showStable", { n: g.length }) : t("hideStable")}</button>` : ""}</div>`;
    if (!folded) html += g.map(personRow).join("");
  });
  box.innerHTML = html;
  const f = $("#fold"); if (f) f.onclick = () => { S.showStable = !S.showStable; drawList(); };
}

function confText(c) { const m = String(c || "").match(/^(\w+)\s*(?:\((.*)\))?/); if (!m) return ""; return `${has("conf" + m[1]) ? t("conf" + m[1]) : m[1]}${m[2] && lang !== "hi" ? ` · ${m[2]}` : ""}`; }
function lastOf(arr) { if (!arr) return null; for (let i = arr.length - 1; i >= 0; i--) if (arr[i] !== null && arr[i] !== undefined) return { v: arr[i], i }; return null; }
function mean(arr) { const n = (arr || []).filter((x) => x !== null && x !== undefined); return n.length ? n.reduce((a, b) => a + Number(b), 0) / n.length : null; }

function drawDetail() {
  const box = $("#detail"); if (!box) return;
  const s = S.queue && S.queue.find((x) => x.senior_id === S.selected);
  if (!s) { box.innerHTML = `<div class="empty">${ico("users", "xl")}<h3>${t("allPeople")}</h3><p class="sm">${L("Choose someone from the list to see why they're on it and what to do next.", "सूची से किसी को चुनें और देखें कि वे क्यों हैं और आगे क्या करना है।")}</p></div>`; return; }
  const d = S.detail, v = s.current_vitals || {}, tl = d ? d.timeline_14d : null, x = TIER[s.tier] || TIER.GREEN;
  const factors = (s.factors || []).filter((f) => f.points > 0).slice(0, 6), maxPts = Math.max(...factors.map((f) => f.points), 1);
  const srcOf = (f) => (f.code === "ml_pattern" ? t("fromModel") : String(f.code).startsWith("nlp_") ? t("fromCall") : "") + (f.learned_weight && f.learned_weight < 1 ? `${f.code === "ml_pattern" || String(f.code).startsWith("nlp_") ? " · " : ""}${t("downWeighted")}` : "");

  // readings: current value, 14-day average and trend; BP/sugar/weight fall back to the last recorded value
  const tile = (icon, label, val, unit, series, digits, note) => {
    const has = val !== null && val !== undefined && val !== "";
    const avg = series ? mean(series) : null;
    const cmp = note || (has && avg !== null && series.filter((y) => y !== null).length > 2 ? `${t("avg14")} <b class="num">${fmt(avg, digits)}</b>` : "");
    return `<div class="tile"><div class="k">${ico(icon, "s")}${label}</div>
      ${has ? `<div class="v">${val}${unit ? `<small>${unit}</small>` : ""}</div>` : `<div class="v none">${t("notRec")}</div>`}
      ${cmp ? `<div class="cmp">${cmp}</div>` : ""}</div>`;
  };
  const bpLast = tl ? lastOf(tl.bp_sys) : null, sugarLast = tl ? lastOf(tl.sugar) : null, wLast = tl ? lastOf(tl.weight) : null;
  const ago = (o) => (o && tl ? `${t("lastRec")} ${tl.steps ? rel(Date.now() - (tl.steps.length - 1 - o.i) * 86400000) : ""}` : "");
  const bpVal = v.bp || (bpLast ? `${bpLast.v}/${tl.bp_dia[bpLast.i] ?? "–"}` : null);
  const sugarVal = v.sugar ? fmt(v.sugar) : sugarLast ? fmt(sugarLast.v) : null;
  const wVal = v.weight ? fmt(v.weight, 1) : wLast ? fmt(wLast.v, 1) : null;
  const srcKey = "src_" + (v.source || "none");
  const srcLine = `${ico(v.source === "watch" ? "watch" : "info", "s")}<span>${has(srcKey) ? t(srcKey) : esc(v.source)}${v.sync_age_s !== null && v.sync_age_s !== undefined ? ` · ${t("synced")} ${esc(ageRel(v.sync_age_s))}` : ""}${v.battery ? ` · ${L("watch battery", "घड़ी बैटरी")} ${esc(v.battery)}%` : ""}</span>`;

  box.innerHTML = `<div class="dh">
      <div class="who"><div class="grow"><div class="row wrap" style="gap:var(--s2) var(--s3)"><h2>${esc(s.name)}</h2>${badge(s.tier)}${s.sos.active ? `<span class="badge crit">${ico("warn")}SOS</span>` : ""}</div>
        <div class="facts"><span>${esc(s.age)} ${L("yrs", "वर्ष")}</span><span>${esc(titleCase(s.city))}</span><span>${ico("shield", "s")}${esc(confText(s.confidence))}</span></div></div>
        ${Charts.gauge(s.risk_score, { color: VIZ[s.tier] || VIZ.GREEN, label: t("priority"), sub: `${t("priority")} · ${t("outOf")}` })}</div>
      <div class="actions"><button class="btn primary" id="bCall">${ico("phone", "s")}${t("callNow")}</button><button class="btn secondary" id="bLog">${ico("check", "s")}${t("logFollow")}</button><button class="btn secondary" id="bRep">${ico("list", "s")}${L("Doctor report", "डॉक्टर रिपोर्ट")}</button></div></div>
    <div class="ds"><div class="overline">${t("nextStep")}</div><div class="next">${ico("bulb")}<div>${esc(L(s.recommended_action_en, s.recommended_action_hi))}</div></div></div>
    <div class="ds"><div class="overline">${ico("clock", "s")}${t("schedTitle")}</div>${scheduleHtml(d)}</div>
    ${sosLocHtml(s, d)}
    <div class="ds"><div class="overline">${t("whyList")}</div>${factors.length ? Charts.bars(factors.map((f) => ({ label: L(f.en, f.hi), note: srcOf(f), value: f.points, color: VIZ[s.tier] || VIZ.GREEN })),
      { unit: L(" pts", " अंक"), label: t("whyList") }) : `<p class="sm muted">${t("nothingYet")}</p>`}</div>
    <div class="ds"><div class="overline">${t("readings")}</div>
      <div class="tiles">
        ${tile("steps", t("steps"), v.steps !== null && v.steps !== undefined ? fmt(v.steps) : null, "", tl && tl.steps, 0)}
        ${tile("heart", t("heart"), v.live_hr || v.resting_hr ? fmt(v.live_hr || v.resting_hr) : null, "bpm", tl && tl.heart_rate, 0)}
        ${tile("drop", t("oxygen"), v.spo2 ? fmt(v.spo2, 1) : null, "%", tl && tl.spo2, 1)}
        ${tile("gauge", t("bp"), bpVal ? esc(bpVal) : null, "mmHg", tl && tl.bp_sys, 0, !v.bp && bpLast ? ago(bpLast) : "")}
        ${tile("sugar", t("sugar"), sugarVal, "mg/dL", tl && tl.sugar, 0, !v.sugar && sugarLast ? ago(sugarLast) : "")}
        ${tile("weight", t("weight"), wVal, "kg", tl && tl.weight, 1, !v.weight && wLast ? ago(wLast) : "")}
        ${tile("moon", t("sleep"), v.sleep_hours ? fmt(v.sleep_hours, 1) : null, L("h", "घं"), tl && tl.sleep, 1)}
      </div><div class="source">${srcLine}</div>
      <div id="vitFig">${vitalsFig(tl)}</div></div>
    <div class="ds"><div class="overline">${ico("bulb", "s")}${L("Memory & mood, from their calls", "याददाश्त और मूड, कॉल से")}</div>${speechHtml(d)}</div>
    <div class="ds"><div class="overline">${ico("pill", "s")}${L("Medicines", "दवाइयाँ")}</div>${medsHtml(d)}</div>
    <div class="ds"><div class="overline">${ico("users", "s")}${L("Family & contacts", "परिवार और संपर्क")}</div>${contactsHtml(d)}</div>
    <div class="ds"><div class="overline">${t("activity")}</div>${activity(d)}</div>`;
  $("#bCall").onclick = () => startCall(s);
  $("#bLog").onclick = () => followupDialog(s);
  $("#bRep").onclick = () => doctorReport(s);
  bindSchedule(s); bindCallMode(s); bindVitals(tl); bindMeds(s); bindContacts(s);
  const sm = $("#sosMap"); if (sm) streetMap(sm, [{ lat: +sm.dataset.lat, lon: +sm.dataset.lon, label: s.name }]);
  vizDone(box);
}

/* ---------------- vitals over 14 days: one measure at a time (tabs), usual range shaded, clinical lines dashed */
function vitalsDefs(tl) {
  return [
    ["steps", t("steps"), tl.steps, "", 0, null],
    ["heart", t("heart"), tl.heart_rate, "bpm", 0, [60, 100]],
    ["oxygen", t("oxygen"), tl.spo2, "%", 1, [95]],
    ["bp", t("bp"), tl.bp_sys, "mmHg", 0, [140, 90], { label: L("lower", "नीचे"), values: tl.bp_dia, color: "var(--viz-brand-2)" }],
    ["sugar", t("sugar"), tl.sugar, "mg/dL", 0, [70, 140]],
    ["weight", t("weight"), tl.weight, "kg", 1, null],
    ["sleep", t("sleep"), tl.sleep, L("h", "घं"), 1, [7]],
  ].filter((v) => (v[2] || []).filter((x) => x !== null && x !== undefined).length >= 2);
}
function vitalsFig(tl) {
  if (!tl) return `<span class="skel" style="height:140px;width:100%;margin-top:12px"></span>`;
  const defs = vitalsDefs(tl); if (!defs.length) return "";
  if (!defs.some((v) => v[0] === S.vital)) S.vital = defs[0][0];
  const v = defs.find((x) => x[0] === S.vital), vals = v[2];
  const dates = daysBack(vals.length).map(dayLabel);
  // the person's usual range: mean ± 1 SD of the earlier days (the last 3 days are what we compare)
  const base = vals.slice(0, -3).filter((x) => x !== null && x !== undefined).map(Number);
  const m = base.length > 3 ? base.reduce((a, b) => a + b, 0) / base.length : null;
  const sd = m === null ? 0 : Math.sqrt(base.reduce((a, b) => a + (b - m) ** 2, 0) / base.length);
  const band = m === null ? null : [m - sd, m + sd];
  const last = lastOf(vals);
  const note = `${last ? `${L("Latest", "ताज़ा")} <b class="num">${fmt(last.v, v[4])}</b> ${esc(v[3])}` : ""}${band ? ` · ${L("usual", "सामान्यतः")} <span class="num">${fmt(band[0], v[4])}–${fmt(band[1], v[4])}</span>` : ""}`;
  const tabs = `<div class="vit-tabs" role="tablist" aria-label="${L("Readings over 14 days", "14 दिन की रीडिंग")}">${defs.map((x) =>
    `<button type="button" role="tab" data-vit="${x[0]}" aria-selected="${x[0] === S.vital}">${esc(x[1])}</button>`).join("")}</div>`;
  const chart = Charts.line(vals, { labels: dates, band, ref: v[5], unit: v[3], digits: v[4], second: v[6] || null, width: innerWidth < 600 ? 340 : 460,
    label: `${v[1]}, ${L("last 14 days", "पिछले 14 दिन")}. ${note.replace(/<[^>]+>/g, "")}` });
  return Charts.figure({ title: L("Last 14 days", "पिछले 14 दिन"), sub: note, actions: "", cls: "vit",
    body: tabs + chart + `<p class="viz-key xs muted"><span class="k-band"></span>${L("their usual range", "उनकी सामान्य सीमा")}${v[5] ? `<span class="k-ref"></span>${L("clinical guide line", "चिकित्सीय सीमा")}` : ""}</p>`,
    table: { head: [L("Day", "दिन"), v[1]], rows: vals.map((x, i) => [dates[i], x === null || x === undefined ? "–" : fmt(x, v[4]) + (v[6] && v[6].values[i] ? "/" + v[6].values[i] : "")]) } });
}
/* ---------------- memory & mood: signs from how they talk on their check-in calls (engine/speech_signals.py) */
function speechHtml(d) {
  if (!d) return `<span class="skel" style="height:14px;width:60%"></span>`;
  const sp = d.speech || {};
  if (!sp.calls || sp.cognition === "not_enough") return `<p class="sm muted">${L("Saathi learns how they usually talk from their check-in calls. Signs appear after a few calls.", "साथी चेक-इन कॉल से सीखता है कि वे आमतौर पर कैसे बात करते हैं। कुछ कॉल के बाद संकेत दिखेंगे।")}</p>`;
  const cog = sp.cognition === "watch" ? `<span class="badge high">${ico("alert")}${L("Memory: worth a check", "याददाश्त: जाँच ठीक रहेगी")}</span>` : `<span class="badge ok">${L("Memory: steady", "याददाश्त: सामान्य")}</span>`;
  const mood = sp.mood === "low" ? `<span class="badge watch">${L("Mood: low lately", "मूड: हाल में उदास")}</span>` : `<span class="badge ok">${L("Mood: steady", "मूड: सामान्य")}</span>`;
  const flags = (sp.flags || []).map((f) => `<li>${ico(f.kind === "mood" ? "heart" : "bulb", "s")}<span>${esc(L(f.en, f.hi))}</span></li>`).join("");
  const advice = sp.advice_en ? `<div class="next" style="margin-top:10px">${ico("info")}<div>${esc(L(sp.advice_en, sp.advice_hi))}</div></div>` : "";
  const ser = sp.series || [], vals = ser.map((x) => x.words_per_answer);
  const base = vals.slice(0, -3).filter((x) => x !== null && x !== undefined);
  const m = base.length > 2 ? base.reduce((a, b) => a + b, 0) / base.length : null;
  const sd = m === null ? 0 : Math.sqrt(base.reduce((a, b) => a + (b - m) ** 2, 0) / base.length);
  const chart = vals.length > 2 ? Charts.figure({ title: L("Words per answer, call by call", "हर जवाब में शब्द, कॉल दर कॉल"), sub: L("Shorter answers over time can be an early sign of memory or mood change.", "समय के साथ छोटे जवाब याददाश्त या मूड बदलने का शुरुआती संकेत हो सकते हैं।"), actions: "", cls: "vit",
    body: Charts.line(vals, { labels: ser.map((x) => x.date.slice(5)), band: m === null ? null : [m - sd, m + sd], unit: L("words", "शब्द"), digits: 1, width: innerWidth < 600 ? 340 : 460,
      label: L("Words per answer on each call", "हर कॉल में प्रति जवाब शब्द") }) + `<p class="viz-key xs muted"><span class="k-band"></span>${L("their usual range", "उनकी सामान्य सीमा")}</p>`,
    table: { head: [L("Call", "कॉल"), L("Words per answer", "प्रति जवाब शब्द"), L("Mood", "मूड")], rows: ser.map((x) => [x.date, fmt(x.words_per_answer, 1), x.mood > 0 ? "🙂" : x.mood < 0 ? "☹" : "–"]) } }) : "";
  return `<div class="row wrap" style="gap:8px">${cog}${mood}</div>${flags ? `<ul class="sig-list">${flags}</ul>` : `<p class="sm muted" style="margin-top:8px">${L("Talking as usual on recent calls.", "हाल की कॉल में सामान्य बातचीत।")}</p>`}${advice}
    <div style="margin-top:12px">${chart}</div><p class="xs subtle" style="margin-top:6px">${L(`From ${sp.calls} calls. A screening signal for you, not a diagnosis.`, `${sp.calls} कॉल से। यह आपके लिए संकेत है, निदान नहीं।`)}</p>`;
}
function bindVitals(tl) {
  const box = $("#vitFig"); if (!box || !tl) return;
  box.onclick = (e) => { const b = e.target.closest("[data-vit]"); if (!b) return; S.vital = b.dataset.vit; box.innerHTML = vitalsFig(tl); vizDone(box); box.querySelector(`[data-vit="${S.vital}"]`).focus(); };
}

/* ---------------- SOS: where it was pressed (only while the alert is open or in the last day) */
function sosLocHtml(s, d) {
  const e = d && (d.sos || []).find((x) => x.lat !== null && x.lat !== undefined && (x.status === "active" || Date.now() - (parseTime(x.time) || 0) < 86400000));
  if (!e) return "";
  return `<div class="ds sos-loc"><div class="overline">${ico("pin", "s")}${L("Where the alert came from", "अलर्ट कहाँ से आया")} · ${esc(rel(e.time))}</div>
    <div class="map-box" id="sosMap" data-lat="${esc(e.lat)}" data-lon="${esc(e.lon)}" role="img" aria-label="${L("Map of the alert location", "अलर्ट की जगह का नक्शा")}">
      <p class="sm muted map-off">${L("Map needs internet.", "नक्शे के लिए इंटरनेट चाहिए।")} <span class="num">${Number(e.lat).toFixed(5)}, ${Number(e.lon).toFixed(5)}</span></p></div>
    <a class="link" href="${gmaps(e.lat, e.lon)}" target="_blank" rel="noopener">${ico("pin", "s")}${L("Open in maps", "मैप में खोलें")}</a></div>`;
}

/* ---------------- medicines: 14-day calendar per medicine + the care manager's editor */
function medsHtml(d) {
  if (!d) return `<span class="skel" style="height:14px;width:50%"></span>`;
  const m = d.medicines || { medicines: [], dates: [] };
  const word = { taken: L("taken", "ली"), skipped: L("not taken", "नहीं ली"), missed: L("missed", "छूटी"), due: L("due", "बाकी"), none: L("not set yet", "तय नहीं") };
  let body = "";
  if (m.medicines.length) {
    const cols = m.dates.map((x) => new Date(x + "T12:00:00").getDate());
    const rows = m.medicines.map((med) => ({
      label: med.name, sub: `${med.dose_text ? med.dose_text + " · " : ""}${med.times.join(", ")}`,
      cells: med.days.map((day) => {
        const st = day.doses.map((x) => x.status), counted = st.filter((x) => x !== "none");
        const state = !counted.length ? "none" : st.includes("missed") ? "missed" : st.includes("skipped") ? "skipped" : st.includes("due") ? "due" : "taken";
        return { state, parts: day.doses.length > 1 ? `<i class="dd">${day.doses.map((x) => `<b class="${x.status}"></b>`).join("")}</i>` : "",
          tip: `${dayLabel(day.date)}: ${day.doses.map((x) => `${x.time} ${word[x.status] || x.status}`).join(", ")}` };
      }),
    }));
    body = `<div class="meds-top"><div class="big-n num">${m.adherence_pct === null ? "–" : m.adherence_pct + "%"}</div><p class="sm muted">${L("of doses taken in 14 days", "14 दिनों में ली गई ख़ुराक")}</p>
        ${m.missed_in_a_row ? `<span class="badge high">${ico("alert")}${L("Last two doses not taken", "पिछली दो ख़ुराक नहीं लीं")}</span>` : ""}</div>
      ${Charts.heat(rows, cols, { label: L("Doses over the last 14 days", "पिछले 14 दिनों की ख़ुराक") })}
      <p class="viz-key xs muted"><span class="hk taken"></span>${word.taken}<span class="hk skipped"></span>${word.skipped}<span class="hk missed"></span>${word.missed}<span class="hk due"></span>${word.due}</p>
      <ul class="chips">${m.medicines.map((med) => `<li class="sched">${ico("pill", "s")}<b>${esc(med.name)}</b><span class="subtle xs">${esc(med.times.join(", "))}</span>
        <button class="btn quiet icon" data-med-del="${esc(med.id)}" aria-label="${L("Remove", "हटाएँ")} ${esc(med.name)}">${ico("close", "s")}</button></li>`).join("")}</ul>`;
  } else {
    body = `<p class="sm muted">${L("No medicines yet. Add them here and the phone will ring at each time with a big “Taken” button.", "अभी कोई दवा नहीं। यहाँ जोड़ें, हर समय पर फ़ोन बजेगा और बड़ा “ले ली” बटन दिखेगा।")}</p>`;
  }
  return body + `<form class="mini-form" id="medForm"><input class="input" name="name" required placeholder="${L("Medicine name", "दवा का नाम")}" aria-label="${L("Medicine name", "दवा का नाम")}">
    <input class="input" name="dose" placeholder="${L("Dose, as prescribed", "ख़ुराक, पर्चे के अनुसार")}" aria-label="${L("Dose", "ख़ुराक")}">
    <input class="input" name="times" required placeholder="08:00, 20:00" aria-label="${L("Times of day", "दिन के समय")}" pattern="[0-9:, ]+">
    <button class="btn secondary">${ico("plus", "s")}${L("Add", "जोड़ें")}</button></form>`;
}
function bindMeds(s) {
  const f = $("#medForm"); if (!f) return;
  f.onsubmit = async (e) => {
    e.preventDefault();
    const times = f.times.value.split(/[ ,]+/).filter(Boolean);
    try {
      await api(`/api/seniors/${encodeURIComponent(s.senior_id)}/medicines`, { method: "POST", body: JSON.stringify({ name: f.name.value, dose_text: f.dose.value, times }) });
      toast(L("Medicine added. The phone will ring at those times.", "दवा जोड़ दी। उन समयों पर फ़ोन बजेगा।")); S.detailHash = ""; loadDetail(true);
    } catch (err) { toast(err.message, "err"); }
  };
  $("#detail").querySelectorAll("[data-med-del]").forEach((b) => (b.onclick = async () => {
    try { await api(`/api/seniors/${encodeURIComponent(s.senior_id)}/medicines/${encodeURIComponent(b.dataset.medDel)}`, { method: "DELETE" }); toast(L("Medicine removed", "दवा हटा दी")); S.detailHash = ""; loadDetail(true); }
    catch (err) { toast(err.message, "err"); }
  }));
}

/* ---------------- family & contacts shown on the senior's phone, one tap to call */
function contactsHtml(d) {
  if (!d) return `<span class="skel" style="height:14px;width:50%"></span>`;
  const list = (d.contacts || []).filter((c) => c.id !== "emergency");
  return `${list.length ? `<ul class="contacts">${list.map((c) => `<li><span class="av">${esc(initials(c.name))}</span><div class="grow"><b>${esc(c.name)}</b>
      <span class="sm muted">${esc(c.relation || "")}${c.is_emergency ? ` · <span class="badge crit">${L("Emergency", "आपातकाल")}</span>` : ""}</span></div>
      <a class="link num" href="tel:${esc(String(c.phone).replace(/\s/g, ""))}">${esc(c.phone)}</a>
      <button class="btn quiet icon" data-ct-del="${esc(c.id)}" aria-label="${L("Remove", "हटाएँ")} ${esc(c.name)}">${ico("close", "s")}</button></li>`).join("")}</ul>`
    : `<p class="sm muted">${L("No family numbers yet. They appear on the phone's Family tab with a big Call button.", "अभी परिवार के नंबर नहीं। ये फ़ोन के ‘परिवार’ टैब पर बड़े कॉल बटन के साथ दिखेंगे।")}</p>`}
    <form class="mini-form" id="ctForm"><input class="input" name="name" required placeholder="${L("Name", "नाम")}" aria-label="${L("Name", "नाम")}">
      <input class="input" name="relation" placeholder="${L("Relation (Son, Neighbour…)", "रिश्ता (बेटा, पड़ोसी…)")}" aria-label="${L("Relation", "रिश्ता")}">
      <input class="input" name="phone" required type="tel" placeholder="+91 …" aria-label="${L("Phone", "फ़ोन")}">
      <label class="check"><input type="checkbox" name="em"> ${L("Emergency", "आपातकाल")}</label>
      <button class="btn secondary">${ico("plus", "s")}${L("Add", "जोड़ें")}</button></form>`;
}
function bindContacts(s) {
  const f = $("#ctForm"); if (!f) return;
  f.onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(`/api/seniors/${encodeURIComponent(s.senior_id)}/contacts`, { method: "POST", body: JSON.stringify({ name: f.name.value, relation: f.relation.value, phone: f.phone.value, is_emergency: f.em.checked }) });
      toast(L("Contact added to their phone", "संपर्क उनके फ़ोन में जुड़ गया")); S.detailHash = ""; loadDetail(true);
    } catch (err) { toast(err.message, "err"); }
  };
  $("#detail").querySelectorAll("[data-ct-del]").forEach((b) => (b.onclick = async () => {
    try { await api(`/api/seniors/${encodeURIComponent(s.senior_id)}/contacts/${encodeURIComponent(b.dataset.ctDel)}`, { method: "DELETE" }); S.detailHash = ""; loadDetail(true); }
    catch (err) { toast(err.message, "err"); }
  }));
}
function scheduleHtml(d) {
  if (!d) return `<span class="skel" style="height:14px;width:50%"></span>`;
  const list = d.schedules || [];
  const chips = list.map((e) => {
    const call = e.last_call_id && (d.calls || []).find((c) => c.call_id === e.last_call_id);
    return `<span class="sched">${ico("phone", "s")}<b>${esc(t("schedEvery", { t: e.schedule_time }))}</b>${call ? `<span class="subtle xs">${esc(t("schedLast", { w: rel(call.start_time) }))} · ${esc(has("st_" + call.status) ? t("st_" + call.status) : call.status)}</span>` : ""}
      <button class="btn quiet icon" data-del="${esc(e.schedule_id)}" aria-label="${esc(t("schedRemove", { t: e.schedule_time }))}">${ico("close", "s")}</button></span>`;
  }).join("");
  return `${list.length ? `<div class="sched-list">${chips}</div>` : `<p class="sm muted">${t("schedNone")}</p>`}
    <div class="row wrap" style="margin-top:10px"><input class="input" id="schedTime" type="time" value="09:30" aria-label="${t("schedTitle")}" style="width:150px">
    <button class="btn secondary" id="schedAdd">${ico("check", "s")}${t("schedAdd")}</button></div>${callModeHtml(d)}`;
}
// how Saathi reaches them: a basic phone is rung on its number; a smartphone is called inside the Saathi app
function callModeHtml(d) {
  const p = (d && d.senior) || {}, mode = p.call_mode || "app";
  const note = mode === "phone"
    ? (!p.has_number ? L("No phone number saved, so calls cannot ring this phone.", "कोई फ़ोन नंबर सहेजा नहीं है, इसलिए कॉल इस फ़ोन पर नहीं जा सकती।")
      : L("Saathi rings their number like a normal call. If Sarvam is out of credit, the call goes to the app if it is open.", "साथी उनके नंबर पर सामान्य कॉल करता है। Sarvam बैलेंस ख़त्म होने पर, ऐप खुला हो तो कॉल ऐप में जाती है।"))
    : p.app_online ? L("The Saathi app is online: calls ring inside the app, with no phone charges.", "साथी ऐप ऑनलाइन है: कॉल ऐप के अंदर आती है, फ़ोन का कोई शुल्क नहीं।")
      : L("The Saathi app is offline right now, so Saathi rings their number instead.", "साथी ऐप अभी ऑफ़लाइन है, इसलिए साथी उनके नंबर पर कॉल करेगा।");
  const dot = mode === "app" ? `<span class="dot ${p.app_online ? "ok" : "watch"}" aria-hidden="true"></span>` : "";
  return `<div class="field" style="margin-top:14px"><span class="label">${L("How Saathi calls", "साथी कैसे कॉल करे")}</span>
    <div class="seg" role="group" aria-label="${L("How Saathi calls", "साथी कैसे कॉल करे")}" id="callMode">
      <button type="button" data-m="app" aria-pressed="${mode === "app"}">${L("Smartphone (in app)", "स्मार्टफ़ोन (ऐप में)")}</button>
      <button type="button" data-m="phone" aria-pressed="${mode === "phone"}">${L("Basic phone (normal call)", "साधारण फ़ोन (सामान्य कॉल)")}</button></div>
    <p class="xs subtle row" style="gap:6px;margin-top:6px">${dot}<span>${esc(note)}</span></p></div>
    <label class="field" style="margin-top:12px"><span class="label">${L("Language Saathi speaks", "साथी किस भाषा में बात करे")}</span>
      <select class="input" id="callLang" style="max-width:260px">${CALL_LANGS.map(([c, n]) => `<option value="${c}" ${(p.language || "hi") === c ? "selected" : ""}>${n}</option>`).join("")}</select></label>`;
}
const CALL_LANGS = [["hi", "हिंदी · Hindi"], ["en", "English"], ["bn", "বাংলা · Bengali"], ["gu", "ગુજરાતી · Gujarati"], ["kn", "ಕನ್ನಡ · Kannada"], ["ml", "മലയാളം · Malayalam"],
  ["mr", "मराठी · Marathi"], ["od", "ଓଡ଼ିଆ · Odia"], ["pa", "ਪੰਜਾਬੀ · Punjabi"], ["ta", "தமிழ் · Tamil"], ["te", "తెలుగు · Telugu"]];
function bindCallMode(s) {
  const ls = $("#callLang");
  if (ls) ls.onchange = async () => {
    try { const r = await api(`/api/coordinator/seniors/${encodeURIComponent(s.senior_id)}/language`, { method: "POST", body: JSON.stringify({ language: ls.value }) });
      toast(L(`Saathi will speak ${r.name} on their calls`, `साथी उनकी कॉल में ${r.name} बोलेगा`)); S.detailHash = ""; loadDetail(true); }
    catch (err) { toast(err.message, "err"); }
  };
  const g = $("#callMode"); if (!g) return;
  g.onclick = async (e) => {
    const b = e.target.closest("button[data-m]"); if (!b || b.getAttribute("aria-pressed") === "true") return;
    b.setAttribute("aria-busy", "true");
    try { await api(`/api/coordinator/seniors/${encodeURIComponent(s.senior_id)}/call-mode`, { method: "POST", body: JSON.stringify({ call_mode: b.dataset.m }) });
      toast(b.dataset.m === "phone" ? L("Saathi will ring their phone number", "साथी उनके फ़ोन नंबर पर कॉल करेगा") : L("Saathi will call inside the app", "साथी ऐप के अंदर कॉल करेगा"));
      S.detailHash = ""; loadDetail(true); }
    catch (err) { b.removeAttribute("aria-busy"); toast(err.message, "err"); }
  };
}
function bindSchedule(s) {
  const add = $("#schedAdd"); if (!add) return;
  add.onclick = async () => {
    const v = $("#schedTime").value; if (!v) return;
    add.setAttribute("aria-busy", "true");
    try { await api("/api/calls/schedule", { method: "POST", body: JSON.stringify({ senior_id: s.senior_id, schedule_time: v, recurring: true }) }); toast(t("schedSaved", { t: v })); S.detailHash = ""; loadDetail(true); }
    catch (e) { add.removeAttribute("aria-busy"); toast(e.message, "err"); }
  };
  $("#detail").querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    try { await api(`/api/calls/schedule/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" }); toast(t("schedRemoved")); S.detailHash = ""; loadDetail(true); }
    catch (e) { toast(e.message, "err"); }
  }));
}
function activity(d) {
  if (!d) return `<span class="skel" style="height:14px;width:60%"></span><span class="skel" style="height:14px;width:40%;margin-top:10px"></span>`;
  const items = [];
  d.calls.slice(0, 5).forEach((c) => {
    const st = has("st_" + c.status) ? t("st_" + c.status) : c.status;
    const cues = (c.symptoms_reported || []).join(", ");
    // the AI's notes for the care manager (written after the call when the conversation model is on)
    const aiSum = L(c.ai_summary_en, c.ai_summary_hi);
    const notes = aiSum ? `<div class="callnote">${c.mood && has("mood_" + c.mood) ? `<span class="badge ${c.mood === "good" ? "ok" : c.mood === "okay" ? "" : "high"}">${t("mood_" + c.mood)}</span> ` : ""}${esc(aiSum)}
      ${(c.concerns || []).length ? `<div class="sm" style="margin-top:4px"><b>${t("concernsW")}:</b> ${esc(c.concerns.join("; "))}</div>` : ""}
      ${c.encouragement ? `<div class="sm subtle" style="margin-top:2px">${t("encouragedW")}: ${esc(c.encouragement)}</div>` : ""}</div>` : "";
    items.push([c.start_time, c.escalation_flag ? "crit" : "", "phone", `<b>${t("callWord")}</b> · ${esc(st)}`, `${esc(cues || t("cuesNone"))}${c.escalation_flag ? ` · <span style="color:var(--crit-ink)">${t("escalated")}</span>` : ""}${notes}`,
      c.transcript && c.transcript.length ? `<details class="tx"><summary>${t("transcript")}</summary>${c.transcript.map((m) => `<div class="bub ${m.speaker === "ai" ? "" : "me"}">${esc(m.text)}</div>`).join("")}</details>` : ""]);
  });
  d.sos.slice(0, 3).forEach((e) => items.push([e.time, "crit", "warn", `<b>${t("alertWord")}</b> · ${esc(has("st_" + e.status) ? t("st_" + e.status) : e.status)}`, esc(has("src_" + e.source) ? t("src_" + e.source) : e.source || ""), ""]));
  d.actions.slice(0, 5).forEach((a) => items.push([a.timestamp, "ok", "check", `<b>${t("followWord")}</b> · ${esc(has("act_" + a.action_taken) ? t("act_" + a.action_taken) : a.action_taken)}`,
    `${esc(has("out_" + a.outcome) ? t("out_" + a.outcome) : a.outcome)}${a.feedback ? ` · ${esc(has("fb_" + a.feedback) ? t("fb_" + a.feedback) : a.feedback)}` : ""}${a.notes ? ` · “${esc(a.notes)}”` : ""}`, ""]));
  items.sort((a, b) => (parseTime(b[0]) || 0) - (parseTime(a[0]) || 0));
  if (!items.length) return `<p class="muted sm">${t("nothingYet")}</p>`;
  return `<ul class="tl">${items.map((i) => `<li><span class="ic ${i[1]}">${ico(i[2], "s")}</span><div><div class="row wrap" style="justify-content:space-between"><span>${i[3]}</span><span class="when" title="${esc(fullTime(i[0]))}">${esc(rel(i[0]))}</span></div><div class="sm muted">${i[4]}</div>${i[5]}</div></li>`).join("")}</ul>`;
}

// ------------------------------------------------------------------------------------------ coordinator: People
function drawPeople() {
  const page = $("#page");
  if (!S.queue) { page.innerHTML = `<div class="card">${skeletonList(8)}</div>`; return; }
  const rows = S.queue.filter(matches);
  page.innerHTML = `<div class="card"><div class="table-wrap"><table class="tbl cards-sm"><thead><tr><th>${t("colName")}</th><th>${t("colStatus")}</th><th>${t("colReason")}</th><th>${t("colCity")}</th><th class="n">${t("colAge")}</th><th class="n">${t("priority")}</th></tr></thead>
    <tbody>${rows.map((s) => `<tr class="click" data-id="${esc(s.senior_id)}" tabindex="0"><td data-l="${t("colName")}"><b>${esc(s.name)}</b></td><td data-l="${t("colStatus")}">${badge(s.tier)}</td>
      <td data-l="${t("colReason")}" class="muted">${esc(L((s.why_today_en || [])[0], (s.why_today_hi || [])[0]))}</td><td data-l="${t("colCity")}">${esc(titleCase(s.city))}</td><td class="n" data-l="${t("colAge")}">${esc(s.age)}</td><td class="n" data-l="${t("priority")}">${esc(s.risk_score)}</td></tr>`).join("")}</tbody></table></div>
    ${rows.length ? "" : `<div class="empty"><img class="empty-ill" src="/static/illustrations/search_empty.svg" alt="" width="360" height="300" decoding="async"><h3>${t("nobody")}</h3><p class="sm">${t("nobodySub")}</p></div>`}</div>`;
  const tb = page.querySelector("tbody");
  const open = (tr) => { if (tr) location.hash = `#/today/${encodeURIComponent(tr.dataset.id)}`; };
  tb.onclick = (e) => open(e.target.closest("tr"));
  tb.onkeydown = (e) => { if (e.key === "Enter") open(e.target.closest("tr")); };
}

// ------------------------------------------------------------------------------------------ dialogs
function dialog(html, label) {
  const prev = document.activeElement;
  const scrim = document.createElement("div"); scrim.className = "scrim";
  scrim.innerHTML = `<div class="dialog" role="dialog" aria-modal="true" aria-label="${esc(label || "")}">${html}</div>`;
  document.body.appendChild(scrim);
  const el = scrim.firstElementChild;
  const close = () => { scrim.remove(); document.removeEventListener("keydown", onKey); if (prev && prev.focus) prev.focus(); api.onClose && api.onClose(); };
  const onKey = (e) => {
    if (e.key === "Escape") close();
    if (e.key === "Tab") { const f = el.querySelectorAll('button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])'); if (!f.length) return; const a = f[0], b = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); b.focus(); } else if (!e.shiftKey && document.activeElement === b) { e.preventDefault(); a.focus(); } }
  };
  document.addEventListener("keydown", onKey);
  scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) close(); });
  el.querySelectorAll("[data-close]").forEach((b) => (b.onclick = close));
  const api = { el, close, onClose: null };
  setTimeout(() => { const f = el.querySelector("input, select, textarea, .btn.primary, [data-close]"); if (f) f.focus(); }, 30);
  return api;
}

async function startCall(s) {
  const d = dialog(`<div class="dlg-h"><div class="grow"><h3>${t("callNow")}</h3><p class="sm subtle">${esc(s.name)}</p></div><button class="btn quiet icon" data-close aria-label="${t("close")}">${ico("close")}</button></div>
    <div class="dlg-b"><div class="call-status"><div class="ring" id="ring">${ico("phone", "xl")}</div><p class="muted" id="cst" role="status">${t("ringingT")}</p></div>
    <div class="live-tx hidden" id="ctx" aria-live="polite"></div><div id="cres"></div></div>
    <div class="dlg-f"><button class="btn secondary" data-close>${t("close")}</button></div>`, t("callNow"));
  let timerId = null; d.onClose = () => { clearInterval(timerId); load(true); };
  const st = $("#cst", d.el), ring = $("#ring", d.el);
  let rec;
  try { rec = await api("/api/calls/initiate", { method: "POST", body: JSON.stringify({ senior_id: s.senior_id }) }); }
  catch (e) { st.textContent = e.message; ring.className = "ring fail"; return; }
  if (!rec.signaled) { st.textContent = rec.note || t("offline"); ring.className = "ring fail"; }
  else if (rec.note) $("#cres", d.el).innerHTML = `<p class="sm subtle">${esc(rec.note)}</p>`;
  timerId = setInterval(async () => {
    if (!document.body.contains(d.el)) return clearInterval(timerId);
    try {
      const c = await api(`/api/calls/state/${rec.call_id}`);
      if (c.status === "connected") {
        st.textContent = t("connected"); const tx = $("#ctx", d.el); tx.classList.remove("hidden");
        tx.innerHTML = (c.transcript || []).map((m) => `<div class="bub ${m.speaker === "ai" ? "" : "me"}">${esc(m.text)}</div>`).join(""); tx.scrollTop = tx.scrollHeight;
      } else if (c.status === "declined" || c.status === "missed") { st.textContent = t(c.status); ring.className = "ring fail"; clearInterval(timerId); }
      else if (c.status === "completed") {
        clearInterval(timerId); st.textContent = t("completedT"); ring.className = "ring done"; ring.innerHTML = ico("check", "xl");
        const meds = c.meds_status === "taken" ? t("taken") : c.meds_status === "skipped" ? t("skipped") : t("unknown");
        $("#cres", d.el).innerHTML = `<div class="result"><ul class="statlist"><li><span>${t("cues")}</span><b>${esc((c.symptoms_reported || []).join(", ") || t("cuesNone"))}</b></li><li><span>${t("meds")}</span><b>${esc(meds)}</b></li></ul>
          ${c.escalation_flag ? `<p class="sm" style="color:var(--crit-ink);margin-top:8px;font-weight:600">${ico("alert", "s")} ${t("escalated")}</p>` : ""}</div>`;
        load(true); loadDetail(true);
      }
    } catch (e) { clearInterval(timerId); }
  }, 1200);
}

function followupDialog(s) {
  let useful = "useful";
  const d = dialog(`<div class="dlg-h"><div class="grow"><h3>${t("followTitle")}</h3><p class="sm subtle">${esc(s.name)}</p></div><button class="btn quiet icon" data-close aria-label="${t("close")}">${ico("close")}</button></div>
    <form class="dlg-b" id="ff">
      <label class="field"><span class="label">${t("action")}</span><select class="input" id="fa">${["call_completed", "nurse_dispatched", "med_reviewed"].map((k) => `<option value="${k}">${t("act_" + k)}</option>`).join("")}</select></label>
      <label class="field"><span class="label">${t("outcome")}</span><select class="input" id="fo">${["no_issue", "issue_confirmed", "escalated"].map((k) => `<option value="${k}">${t("out_" + k)}</option>`).join("")}</select></label>
      <div class="field"><span class="label" id="fuL">${t("useful")}</span><div class="choice" id="fu" role="group" aria-labelledby="fuL">${[["useful", "useYes"], ["not_useful", "useNo"], ["routine", "useRoutine"]].map(([v, k]) => `<button type="button" data-v="${v}" aria-pressed="${v === useful}">${t(k)}</button>`).join("")}</div></div>
      <label class="field"><span class="label">${t("notes")}</span><textarea class="input" id="fn" rows="3"></textarea><span class="help">${t("notesHelp")}</span></label>
    </form>
    <div class="dlg-f"><button class="btn secondary" data-close>${t("cancel")}</button><button class="btn primary" id="fs">${t("save")}</button></div>`, t("followTitle"));
  $("#fu", d.el).onclick = (e) => { const b = e.target.closest("button"); if (!b) return; useful = b.dataset.v; $("#fu", d.el).querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b)); };
  $("#fs", d.el).onclick = async () => {
    const b = $("#fs", d.el); b.setAttribute("aria-busy", "true");
    const codes = (s.factors || []).filter((f) => f.points > 0 && !["data_quality", "learning", "normal"].includes(f.code)).map((f) => f.code);
    try {
      await api("/api/coordinator/action", { method: "POST", body: JSON.stringify({ senior_id: s.senior_id, coordinator_code: S.code, action_taken: $("#fa", d.el).value, outcome: $("#fo", d.el).value, feedback: useful, notes: $("#fn", d.el).value, factor_codes: codes }) });
      d.close(); toast(t("thanks")); S.detailHash = ""; loadDetail(true); load(true);
    } catch (e) { b.removeAttribute("aria-busy"); toast(e.message, "err"); }
  };
}

// ------------------------------------------------------------------------------------------ operations: Overview
const mixBar = (r) => { const tot = r.total || 1; return `<div class="mix" role="img" aria-label="${t("urgent")} ${r.RED}, ${t("attention")} ${r.ORANGE}, ${t("watch")} ${r.YELLOW}, ${t("stable")} ${r.GREEN}">${[["RED", "c"], ["ORANGE", "h"], ["YELLOW", "w"], ["GREEN", "o"]].map(([k, c]) => `<i class="${c}" style="width:${(r[k] / tot) * 100}%"></i>`).join("")}</div>`; };
const legend = () => `<div class="legend">${TIERS.map((k) => `<span><span class="dot ${TIER[k].c}"></span>${t(TIER[k].k)}</span>`).join("")}</div>`;
const workTable = (rows, nameKey, nameLabel) => `<div class="table-wrap"><table class="tbl cards-sm"><thead><tr><th>${nameLabel}</th><th class="n">${t("total")}</th><th class="n">${t("urgent")}</th><th class="n">${t("attention")}</th><th class="n">${t("watch")}</th><th style="width:30%"></th></tr></thead>
  <tbody>${rows.map((r) => `<tr><td data-l="${nameLabel}"><b>${esc(titleCase(r[nameKey]))}</b></td><td class="n" data-l="${t("total")}">${r.total}</td><td class="n" data-l="${t("urgent")}">${r.RED}</td><td class="n" data-l="${t("attention")}">${r.ORANGE}</td><td class="n" data-l="${t("watch")}">${r.YELLOW}</td><td data-l="">${mixBar(r)}</td></tr>`).join("")}</tbody></table></div>`;
const stat = (label, val) => `<li><span class="muted">${label}</span><b>${val}</b></li>`;

function drawOverview() {
  const page = $("#page"), o = S.ops;
  if (!o) { page.innerHTML = `<div class="kpis">${Array.from({ length: 4 }, () => `<div class="card kpi"><span class="skel" style="height:14px;width:60%"></span><span class="skel" style="height:30px;width:40%;margin-top:10px"></span></div>`).join("")}</div>`; return; }
  const sos = Object.assign({ total: 0, active: 0, confirmed: 0, false_alarm: 0, cancelled_by_senior: 0, avg_response_minutes: null }, o.sos);
  const a = Object.assign({ total: 0, alert_action_rate_pct: null, outcomes: {}, feedback: {} }, o.actions);
  const f = Object.assign({ triggers: 0, false_alarm: 0, ok_but_fell: 0, need_help: 0, no_response: 0, false_trigger_pct: null }, o.falls);
  const c = Object.assign({ total: 0, by_status: {}, escalated: 0 }, o.calls);
  const lr = Object.assign({ ratings: 0, reason_multipliers: {} }, o.learning);
  const tot = o.totals || {}, tr = o.trend_14d || { days: [], sos: [], falls: [], calls: [], followups: [] };
  const sum = (arr) => (arr || []).reduce((x, y) => x + y, 0);
  const dates = tr.days.map(dayLabel);
  const tierTable = (rows, key, head) => ({ head: [head, t("total"), t("urgent"), t("attention"), t("watch"), t("stable")], rows: rows.map((r) => [r[key], r.total, r.RED, r.ORANGE, r.YELLOW, r.GREEN]) });

  // hero: the one number that matters today, the mix as a donut, and three compact KPIs
  const kpi = (icon, label, val, sub, trend, cls = "") => `<div class="hk ${cls}"><div class="k">${ico(icon, "s")}${label}</div><div class="v num">${val}</div>${sub ? `<div class="d">${sub}</div>` : ""}${trend || ""}</div>`;
  const hero = `<section class="hero ops-hero">
    <div class="hero-txt"><div class="overline">${L(`Today across ${o.by_city.length} cities`, `आज ${o.by_city.length} शहरों में`)}</div>
      <div class="hero-n num">${fmt(tot.needing_attention)}</div>
      <p>${L("people need a call or visit today", "लोगों को आज कॉल या विज़िट चाहिए")} · ${L("of", "कुल")} <b class="num">${fmt(tot.seniors)}</b> ${L("monitored", "निगरानी में")}${tot.RED ? ` · <b style="color:var(--crit-ink)">${fmt(tot.RED)} ${t("urgent").toLowerCase()}</b>` : ""}</p></div>
    <div class="hero-viz">${Charts.donut({ segments: tierParts(tot), size: 150, thick: 20, center: fmt(tot.seniors), centerSub: L("people", "लोग"),
        label: L("Everyone by priority", "सभी, प्राथमिकता के अनुसार") + ": " + TIERS.map((k) => `${t(TIER[k].k)} ${tot[k] || 0}`).join(", ") })}${tierLegend(tot)}</div>
    <div class="hero-kpis">
      ${kpi("warn", t("openAlerts"), fmt(sos.active), `${fmt(sum(tr.sos))} ${L("in 14 days", "14 दिनों में")}`, Charts.mini(tr.sos, { color: "var(--viz-crit)", label: L("Alerts per day", "रोज़ के अलर्ट") }), sos.active ? "crit" : "")}
      ${kpi("clock", t("avgResp"), sos.avg_response_minutes === null ? "–" : `${fmt(sos.avg_response_minutes, 1)}<small> ${t("minutes")}</small>`, sos.avg_response_minutes === null ? L("No alerts resolved yet", "अभी कोई अलर्ट नहीं सुलझा") : L("to close an alert", "अलर्ट बंद करने में"))}
      ${kpi("check", t("followRate"), a.alert_action_rate_pct === null ? "–" : `${fmt(a.alert_action_rate_pct)}%`, `${fmt(a.total)} ${L("follow-ups logged", "फ़ॉलो-अप दर्ज")}`, Charts.mini(tr.followups, { label: L("Follow-ups per day", "रोज़ के फ़ॉलो-अप") }))}
    </div></section>`;

  // where: India map with a donut per city, and the cities ranked
  const cityRows = o.by_city.map((r) => ({ name: titleCase(r.city), total: r.total, parts: tierParts(r), sub: `${fmt(r.total)} · ${fmt(r.RED + r.ORANGE)} ${L("need care", "को देखभाल")}`,
    tip: `${titleCase(r.city)}: ${r.total} ${L("people", "लोग")} · ${TIERS.map((k) => `${t(TIER[k].k)} ${r[k]}`).join(", ")}` }));
  const mapFig = Charts.figure({ title: L("Where people are", "लोग कहाँ हैं"), sub: L("Circle size = people watched; colours = priority mix", "गोले का आकार = लोगों की संख्या; रंग = प्राथमिकता"),
    body: IndiaMap.render({ cities: cityRows, label: L("Map of India with the cities served", "सेवा वाले शहरों का भारत का नक्शा") }) + tierLegend(tot), cls: "map-fig",
    table: tierTable(o.by_city, "city", t("colCity")) });
  const cityFig = Charts.figure({ title: t("byCity"), sub: L("Sorted by people watched", "लोगों की संख्या के क्रम में"),
    body: Charts.stacks(o.by_city.map((r) => ({ label: titleCase(r.city), parts: tierParts(r) })), { label: t("byCity") }), table: tierTable(o.by_city, "city", t("colCity")) });
  const avgLoad = o.by_coordinator.length ? Math.round(tot.seniors / o.by_coordinator.length) : null;
  const workFig = Charts.figure({ title: t("workload"), sub: avgLoad ? L(`Dashed line = average caseload (${avgLoad})`, `डैश लाइन = औसत (${avgLoad})`) : "",
    body: Charts.stacks(o.by_coordinator.map((r) => ({ label: r.name, parts: tierParts(r) })), { label: t("workload"), target: avgLoad }), table: tierTable(o.by_coordinator, "name", L("Coordinator", "कोऑर्डिनेटर")) });

  // 14 days, one small chart per measure (one axis each; no dual axes)
  const trendCard = (icon, title, vals, color) => `<div class="card pad trend"><div class="row">${ico(icon, "s")}<h3 class="grow">${title}</h3><b class="num">${fmt(sum(vals))}</b></div>
    ${Charts.line(vals, { labels: dates, height: 90, width: 300, color, label: `${title}, ${L("per day, last 14 days", "रोज़, पिछले 14 दिन")}: ${vals.join(", ")}` })}</div>`;
  const trends = `<div><h3 class="sec-h">${L("Last 14 days", "पिछले 14 दिन")}</h3><div class="grid-4">
    ${trendCard("warn", t("emergencies"), tr.sos, "var(--viz-crit)")}${trendCard("fall", t("falls"), tr.falls, "var(--viz-high)")}
    ${trendCard("phone", L("Check-in calls", "चेक-इन कॉल"), tr.calls, "var(--viz-brand)")}${trendCard("check", t("followUps"), tr.followups, "var(--viz-ok)")}</div></div>`;

  // what happened to alerts, falls and calls
  const alertsFig = Charts.figure({ title: t("emergencies"), body: Charts.bars([
      { label: t("totalAlerts"), value: sos.total, color: "var(--viz-neutral)" }, { label: t("confirmedN"), value: sos.confirmed, color: "var(--viz-crit)" },
      { label: t("falseN"), value: sos.false_alarm, color: "var(--viz-ok)" }, { label: t("cancelledN"), value: sos.cancelled_by_senior, color: "var(--viz-watch)" },
      { label: L("Still open", "अभी खुले"), value: sos.active, color: "var(--viz-high)" }], { label: t("emergencies") }) });
  const fallParts = [{ label: t("fOk"), value: f.false_alarm, color: "var(--viz-ok)" }, { label: t("fFellOk"), value: f.ok_but_fell, color: "var(--viz-watch)" },
    { label: t("fHelp"), value: f.need_help, color: "var(--viz-crit)" }, { label: L("No answer", "जवाब नहीं"), value: f.no_response, color: "var(--viz-high)" }];
  const noFalls = `<p class="sm muted">${L("No falls felt by any phone yet. People turn this on in the app's Me tab.", "अभी किसी फ़ोन ने गिरना महसूस नहीं किया। लोग इसे ऐप के ‘मैं’ टैब में चालू करते हैं।")}</p>`;
  const fallsFig = Charts.figure({ title: t("falls"), sub: `${fmt(f.triggers)} ${L("times the phone felt a fall", "बार फ़ोन ने गिरना महसूस किया")}`,
    body: f.triggers ? `<div class="donut-row">${Charts.donut({ segments: fallParts, size: 120, thick: 16, center: fmt(f.triggers), centerSub: L("checks", "जाँच") })}${Charts.legend(fallParts)}</div>` : noFalls });
  const moods = o.moods || {};
  const callsFig = Charts.figure({ title: t("calls"), sub: `${fmt(c.total)} ${L("calls", "कॉल")} · ${fmt(c.escalated)} ${t("escalated").toLowerCase()}`,
    body: Charts.bars(Object.entries(c.by_status).map(([k, n]) => ({ label: has("st_" + k) ? t("st_" + k) : k, value: n })), { label: t("calls") }) +
      (Object.values(moods).some((n) => n) ? `<h4 class="sub-h">${L("How people sounded", "लोग कैसे लगे")}</h4>` + Charts.bars([
        { label: t("mood_good"), value: moods.good || 0, color: "var(--viz-ok)" }, { label: t("mood_okay"), value: moods.okay || 0, color: "var(--viz-neutral)" },
        { label: t("mood_low"), value: moods.low || 0, color: "var(--viz-watch)" }, { label: t("mood_distressed"), value: moods.distressed || 0, color: "var(--viz-crit)" }], { label: L("Mood in calls", "कॉल में मनोदशा") }) : "") });
  const learnFig = `<div class="card pad"><div class="row" style="margin-bottom:12px">${ico("bulb")}<h3>${t("learning")}</h3></div><div class="big-n num">${fmt(lr.ratings)}</div><p class="sm muted">${t("ratings")}</p>
    ${Object.keys(lr.reason_multipliers).length ? `<ul class="statlist" style="margin-top:8px">${Object.entries(lr.reason_multipliers).map(([k, m]) => stat(esc(k.replace(/_/g, " ")), `×${m}`)).join("")}</ul>` : `<p class="sm subtle" style="margin-top:8px">${t("noRatings")}</p>`}</div>`;

  // real street map of recent SOS locations (online only)
  const pins = (o.sos_recent || []).filter((e) => e.lat !== null && e.lat !== undefined);
  const pinKey = pins.map((e) => e.id).join(",");
  const sosFig = pins.length ? Charts.figure({ title: L("Alert locations, last 7 days", "पिछले 7 दिनों के अलर्ट की जगह"), sub: L("From the phone's location when SOS was pressed", "SOS दबाने पर फ़ोन की जगह से"),
    body: `<div class="map-box tall" id="opsMap" data-key="${esc(pinKey)}"><p class="sm muted map-off">${L("Map needs internet.", "नक्शे के लिए इंटरनेट चाहिए।")}</p></div>
      <ul class="pin-list">${pins.map((e) => `<li>${ico("pin", "s")}<b>${esc(e.senior_name)}</b> <span class="muted sm">${esc(rel(e.time))} · ${esc(has("st_" + e.status) ? t("st_" + e.status) : e.status)}</span> <a class="link" href="${gmaps(e.lat, e.lon)}" target="_blank" rel="noopener">${L("Open", "खोलें")}</a></li>`).join("")}</ul>` }) : "";

  const keep = $("#opsMap");   // the street map survives the 8-second refresh when its pins did not change
  page.innerHTML = `<div class="stack-lg">${hero}
    <div class="grid-map">${mapFig}${cityFig}</div>
    ${workFig}${trends}
    <div class="grid-3">${alertsFig}${fallsFig}${callsFig}</div>
    <div class="grid-2">${sosFig || ""}${learnFig}</div></div>`;
  const fresh = $("#opsMap");
  if (fresh && keep && keep.dataset.key === fresh.dataset.key && keep.__map) fresh.replaceWith(keep);
  else if (fresh) streetMap(fresh, pins.map((e) => ({ lat: e.lat, lon: e.lon, label: `${e.senior_name} · ${rel(e.time)}` })));
  vizDone(page);
}

// ------------------------------------------------------------------------------------------ operations: Alert accuracy
function accuracyFig(m) {
  const vs = [["rules_only", t("rulesOnly"), "var(--viz-neutral)"], ["ml_only", t("modelOnly"), "var(--viz-brand-2)"], ["combined", t("combined"), "var(--viz-brand)"]].filter((v) => m.variants[v[0]]);
  const group = (key, title, unit, digits = 0) => `<div><h4 class="sub-h">${title}</h4>${Charts.bars(vs.map((v) => ({ label: v[1], value: m.variants[v[0]][key], color: v[2] })), { unit, digits, label: title, max: unit === "%" ? 100 : undefined })}</div>`;
  return Charts.figure({ title: t("compare"), sub: L("Rules alone, the learned model alone, and both together, on the same cases", "सिर्फ़ नियम, सिर्फ़ मॉडल, और दोनों साथ, एक ही मामलों पर"),
    body: `<div class="grid-2 acc">${group("recall_pct", t("catchRate"), "%")}${group("alert_day_precision_pct", t("precisionK"), "%")}${group("median_lead_days", t("earlyDays"), L(" days", " दिन"))}${group("false_alarms_per_coordinator_week", t("falsePerWk"), "", 2)}</div>`,
    table: { head: ["", t("catchRate"), t("precisionK"), t("earlyDays"), t("falsePerWk")], rows: vs.map((v) => { const x = m.variants[v[0]]; return [v[1], x.recall_pct + "%", x.alert_day_precision_pct + "%", x.median_lead_days, x.false_alarms_per_coordinator_week]; }) } });
}
function drawAccuracy() {
  const page = $("#page"), m = S.metrics;
  if (!m) { page.innerHTML = `<div class="kpis">${Array.from({ length: 4 }, () => `<div class="card kpi"><span class="skel" style="height:14px;width:60%"></span><span class="skel" style="height:30px;width:40%;margin-top:10px"></span></div>`).join("")}</div>`; return; }
  const h = m.variants.combined || m.headline;
  const row = (k, label, hl) => { const x = m.variants[k]; if (!x) return ""; const c = hl ? ' class="n hl"' : ' class="n"'; return `<tr><td data-l="">${hl ? `<b>${label}</b>` : label}</td><td${c} data-l="${t("catchRate")}">${fmt(x.recall_pct)}%</td><td${c} data-l="${t("precisionK")}">${fmt(x.alert_day_precision_pct)}%</td><td${c} data-l="${t("earlyDays")}">${fmt(x.median_lead_days)} ${L("days", "दिन")}</td><td${c} data-l="${t("falsePerWk")}">${fmt(x.false_alarms_per_coordinator_week, 2)}</td></tr>`; };
  page.innerHTML = `<div class="stack-lg">
    <div class="kpis">
      <div class="card kpi"><div class="k">${ico("target", "s")}${t("catchRate")}</div><div class="v">${fmt(h.recall_pct)}%</div><div class="d">${h.detected} ${t("ofCases", { n: h.planted })}</div></div>
      <div class="card kpi"><div class="k">${ico("checkCircle", "s")}${t("precisionK")}</div><div class="v">${fmt(h.alert_day_precision_pct)}%</div><div class="d">${L("of alert days were a real decline", "अलर्ट वाले दिनों में असली गिरावट")}</div></div>
      <div class="card kpi"><div class="k">${ico("clock", "s")}${t("earlyDays")}</div><div class="v">${fmt(h.median_lead_days)}<small class="sm subtle"> ${L("days", "दिन")}</small></div><div class="d">${t("daysEarly")}</div></div>
      <div class="card kpi"><div class="k">${ico("alert", "s")}${t("falsePerWk")}</div><div class="v">${fmt(h.false_alarms_per_coordinator_week, 2)}</div><div class="d">${t("perCoordWk")}</div></div>
    </div>
    ${accuracyFig(m)}
    <div class="card pad"><div class="row" style="margin-bottom:6px">${ico("clock")}<h3>${L("Watch Saathi catch a decline", "देखें साथी ने गिरावट कैसे पकड़ी")}</h3></div>
      <p class="sm muted">${L("Replay one of the simulated decline cases day by day: the readings, what they said on calls, and the moment Saathi alerts the care manager, days before the emergency.", "किसी एक सिम्युलेटेड गिरावट को दिन-ब-दिन दोबारा देखें: रीडिंग, कॉल में कही बातें, और वह पल जब साथी इमरजेंसी से कई दिन पहले केयर मैनेजर को सचेत करता है।")}</p>
      <div class="row wrap" style="gap:8px;margin-top:12px"><select class="input" id="rpCase" style="flex:1;min-width:220px" aria-label="${L("Decline case", "गिरावट का मामला")}"><option>${L("Loading cases…", "मामले लोड हो रहे हैं…")}</option></select>
        <button class="btn primary" id="rpGo" disabled>${ico("chevR", "s")}${L("Play replay", "रीप्ले चलाएँ")}</button></div></div>
    <div class="card" hidden><div class="card-h"><h3>${t("compare")}</h3></div><div class="table-wrap"><table class="tbl cards-sm"><thead><tr><th></th><th class="n">${t("catchRate")}</th><th class="n">${t("precisionK")}</th><th class="n">${t("earlyDays")}</th><th class="n">${t("falsePerWk")}</th></tr></thead>
      <tbody>${row("rules_only", t("rulesOnly"))}${row("ml_only", t("modelOnly"))}${row("combined", t("combined"), true)}</tbody></table></div></div>
    <div class="grid-3">
      <div class="card pad"><div class="row" style="margin-bottom:8px">${ico("mic")}<h3>${t("langTitle")}</h3></div><div class="big-n">${fmt(m.nlp.micro_f1 * 100)}%</div><p class="sm muted">${t("langSub")} · ${m.nlp.examples} ${L("sentences", "वाक्य")}</p></div>
      <div class="card pad"><div class="row" style="margin-bottom:8px">${ico("chart")}<h3>${t("trainedOn")}</h3></div><div class="big-n">${fmt(m.ml_training.training_days)}</div><p class="sm muted">${t("personDays")} · ${fmt(m.ml_training.seniors)} ${L("people", "लोग")}</p></div>
      <div class="card pad"><div class="row" style="margin-bottom:8px">${ico("watch")}<h3>${t("coverage")}</h3></div><div class="big-n">${fmt(m.data_quality_coverage_pct)}%</div><p class="sm muted">${t("coverageSub")}</p></div>
    </div>
    <div class="card"><details class="method"><summary>${ico("chevR", "s")}${t("method")}</summary><ul>
      <li>${t("threshold", { n: m.alert_threshold })} ${L("Evaluation window", "मूल्यांकन अवधि")}: ${esc(m.window)}.</li>${(m.caveats || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ul></details></div>
  </div>`;  bindReplayCard();
}

/* ---------------- doctor report: 30 days on one printable page */
async function doctorReport(s) {
  const w = window.open("", "_blank");             // opened before the await so pop-up blockers allow it
  if (!w) return toast(L("Allow pop-ups to open the report", "रिपोर्ट खोलने के लिए पॉप-अप की अनुमति दें"), "err");
  w.document.write(`<p style="font:16px system-ui;padding:24px">${L("Preparing the report…", "रिपोर्ट तैयार हो रही है…")}</p>`);
  let r; try { r = await api(`/api/senior/${encodeURIComponent(s.senior_id)}/report`); } catch (e) { w.close(); return toast(e.message, "err"); }
  const v = r.vitals, n1 = (x, dg = 0) => (x === null || x === undefined ? "–" : fmt(x, dg));
  const row = (label, st, unit, dg = 0) => !st ? "" : `<tr><td>${label}</td><td>${n1(st.avg, dg)} ${unit}</td><td>${n1(st.min, dg)}–${n1(st.max, dg)}</td><td>${n1(st.first_week, dg)} → <b>${n1(st.last_week, dg)}</b></td><td>${st.n}</td></tr>`;
  const meds = (r.medicines.medicines || []).map((m) => { const st = m.days.flatMap((d) => d.doses.map((x) => x.status)).filter((x) => ["taken", "skipped", "missed"].includes(x));
    const pct = st.length ? Math.round(100 * st.filter((x) => x === "taken").length / st.length) : null;
    return `<tr><td>${esc(m.name)}</td><td>${esc((m.times || []).join(", "))}</td><td>${pct === null ? "–" : pct + "%"}</td></tr>`; }).join("");
  const sp = r.speech || {};
  const html = `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><title>${esc(r.senior.name)} · ${L("Health report", "स्वास्थ्य रिपोर्ट")}</title><style>
    body{font:13px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1d2433;margin:28px auto;max-width:820px;padding:0 20px}
    h1{font-size:22px;margin:0}h2{font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:#0d7a69;border-bottom:1px solid #d7dde5;padding-bottom:4px;margin:22px 0 8px}
    table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:5px 6px;border-bottom:1px solid #eef1f5;vertical-align:top}th{font-size:11px;color:#5b6576;text-transform:uppercase}
    .muted{color:#5b6576}.head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.flag{background:#fff4e5;border-left:3px solid #c66a00;padding:6px 10px;margin:4px 0}
    .btn{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid #0d7a69;background:#0d7a69;color:#fff;cursor:pointer}@media print{.noprint{display:none}body{margin:0}}</style></head><body>
    <div class="head"><div><h1>${esc(r.senior.name)}</h1><div class="muted">${esc(r.senior.age)} ${L("yrs", "वर्ष")} · ${esc(r.senior.gender || "")} · ${esc(titleCase(r.senior.city || ""))}</div>
      <div class="muted">${L("Care manager", "केयर मैनेजर")}: ${esc(r.care_manager.name)} ${esc(r.care_manager.phone)}</div></div>
      <div style="text-align:right"><b>${L("Saathi health report", "साथी स्वास्थ्य रिपोर्ट")}</b><div class="muted">${L("Last 30 days", "पिछले 30 दिन")} · ${esc(r.generated)}</div>
      <button class="btn noprint" onclick="print()" style="margin-top:8px">${L("Print / Save as PDF", "प्रिंट / PDF सहेजें")}</button></div></div>
    <h2>${L("Readings", "रीडिंग")}</h2><table><tr><th>${L("Measure", "माप")}</th><th>${L("Average", "औसत")}</th><th>${L("Range", "सीमा")}</th><th>${L("First week → last week", "पहला हफ़्ता → आख़िरी हफ़्ता")}</th><th>${L("Days", "दिन")}</th></tr>
      ${row(t("steps"), v.steps, "")}${row(L("Resting heart rate", "आराम की धड़कन"), v.resting_hr, "bpm")}${row(t("oxygen"), v.spo2, "%", 1)}${row(t("sleep"), v.sleep_hours, L("h", "घं"), 1)}
      ${row(L("BP systolic", "BP ऊपर"), v.bp_sys, "mmHg")}${row(L("BP diastolic", "BP नीचे"), v.bp_dia, "mmHg")}${row(t("sugar"), v.sugar, "mg/dL")}${row(t("weight"), v.weight, "kg", 1)}</table>
    <h2>${L("Medicines", "दवाइयाँ")}</h2>${meds ? `<table><tr><th>${L("Medicine", "दवा")}</th><th>${L("Times", "समय")}</th><th>${L("Doses taken", "ली गई ख़ुराक")}</th></tr>${meds}</table>` : `<p class="muted">${L("No medicine schedule set in Saathi.", "साथी में दवा का समय तय नहीं है।")}</p>`}
    <h2>${L("Memory & mood (from daily calls)", "याददाश्त और मूड (रोज़ की कॉल से)")}</h2>
      ${(sp.flags || []).length ? sp.flags.map((f) => `<div class="flag">${esc(L(f.en, f.hi))}</div>`).join("") + (sp.advice_en ? `<p>${esc(L(sp.advice_en, sp.advice_hi))}</p>` : "") : `<p class="muted">${sp.calls ? L("No changes noticed.", "कोई बदलाव नहीं दिखा।") : L("Not enough calls yet.", "अभी पर्याप्त कॉल नहीं।")}</p>`}
      <p class="muted" style="font-size:11px">${L("Screening signals from speech patterns on check-in calls; not a diagnosis.", "चेक-इन कॉल में बोलने के तरीक़े से मिले संकेत; निदान नहीं।")}</p>
    <h2>${L("Symptoms mentioned on calls", "कॉल में बताए गए लक्षण")}</h2>${r.symptoms.length ? `<p>${r.symptoms.map(([k, c]) => `${esc(has("cue_" + k) ? t("cue_" + k) : k.replace(/_/g, " "))} ×${c}`).join(" · ")}</p>` : `<p class="muted">${L("None.", "कोई नहीं।")}</p>`}
    <h2>${L("Check-in calls", "चेक-इन कॉल")}</h2>${r.calls.length ? `<table><tr><th>${L("When", "कब")}</th><th>${L("Mood", "मूड")}</th><th>${L("Summary", "सारांश")}</th></tr>${r.calls.map((c) => `<tr><td style="white-space:nowrap">${esc(c.date)}</td><td>${esc(c.mood || c.status || "")}</td><td>${esc(c.summary)}</td></tr>`).join("")}</table>` : `<p class="muted">${L("No calls in this period.", "इस अवधि में कोई कॉल नहीं।")}</p>`}
    ${r.sos.length ? `<h2>${L("Alerts", "अलर्ट")}</h2><table>${r.sos.map((e) => `<tr><td>${esc(e.time || "")}</td><td>${esc(has("src_" + e.source) ? t("src_" + e.source) : e.source)}</td><td>${esc(e.said || "")}</td><td>${esc(e.status)}</td></tr>`).join("")}</table>` : ""}
    ${r.contacts.length ? `<h2>${L("Emergency contacts", "आपातकालीन संपर्क")}</h2><p>${r.contacts.map((c) => `${esc(c.name)} (${esc(c.relation || "")}) ${esc(c.phone || "")}`).join(" · ")}</p>` : ""}
    <p class="muted" style="margin-top:24px;font-size:11px">${L("Prepared by Aegis Saathi from watch readings, medicine answers and daily check-in calls. For the treating doctor's information.", "एजिस साथी द्वारा घड़ी की रीडिंग, दवा के जवाब और रोज़ की कॉल से तैयार। इलाज करने वाले डॉक्टर की जानकारी के लिए।")}</p></body></html>`;
  w.document.open(); w.document.write(html); w.document.close();
}

/* ---------------- replay: one simulated decline case, day by day (engine/replay.py) */
async function bindReplayCard() {
  const sel = $("#rpCase"), go = $("#rpGo"); if (!sel) return;
  try { S.replayCases = S.replayCases || await api("/api/replay/cases"); } catch (e) { sel.innerHTML = `<option>${esc(e.message)}</option>`; return; }
  sel.innerHTML = S.replayCases.map((c) => `<option value="${esc(c.senior_id)}">${esc(c.name)}, ${esc(c.age)} · ${esc(L(c.pattern_en, c.pattern_hi))}${c.lead_days ? ` · ${L(`${c.lead_days} days early`, `${c.lead_days} दिन पहले`)}` : ""}</option>`).join("");
  go.disabled = false; go.onclick = () => replayDialog(sel.value);
}
async function replayDialog(sid) {
  let r; try { r = await api(`/api/replay/${encodeURIComponent(sid)}`); } catch (e) { return toast(e.message, "err"); }
  const n = r.days.length, maxI = n - 1;
  const d = dialog(`<div class="dlg-h"><div class="grow"><h3>${esc(r.name)}, ${esc(r.age)} · ${esc(titleCase(r.city || ""))}</h3><p class="sm subtle">${esc(L(r.pattern_en, r.pattern_hi))}</p></div><button class="btn quiet icon" data-close aria-label="${t("close")}">${ico("close")}</button></div>
    <div class="dlg-b"><div class="row wrap" style="gap:16px;align-items:center"><div id="rpGauge"></div><div class="grow"><div class="overline" id="rpDay"></div><div id="rpBanner" style="margin-top:6px"></div></div></div>
      <div id="rpChart" style="margin-top:12px"></div>
      <div class="row" style="gap:8px;margin-top:10px"><button class="btn secondary icon" id="rpPlay" aria-label="${L("Play or pause", "चलाएँ या रोकें")}">${ico("chevR", "s")}</button>
        <input type="range" id="rpSlide" min="0" max="${maxI}" value="0" style="flex:1" aria-label="${L("Day", "दिन")}"></div>
      <div id="rpToday" style="margin-top:12px"></div><p class="xs subtle" style="margin-top:10px">${esc(r.note)}</p></div>
    <div class="dlg-f"><button class="btn secondary" data-close>${t("close")}</button></div>`, r.name);
  let i = 0, timer = null;
  const dayTxt = (x) => x === 0 ? L("Day of the emergency (without help)", "इमरजेंसी का दिन (मदद न मिलने पर)") : L(`${-x} days before the emergency`, `इमरजेंसी से ${-x} दिन पहले`);
  const chart = (upto) => {
    const W = 520, H = 150, P = { l: 30, r: 8, t: 10, b: 20 }, bw = (W - P.l - P.r) / n, Y = (v) => P.t + (1 - v / 100) * (H - P.t - P.b);
    const bars = r.days.map((x, k) => k > upto ? "" : `<rect x="${(P.l + k * bw + 1).toFixed(1)}" y="${Y(x.risk).toFixed(1)}" width="${Math.max(2, bw - 2).toFixed(1)}" height="${(Y(0) - Y(x.risk)).toFixed(1)}" rx="2" fill="${VIZ[x.tier] || VIZ.GREEN}"><title>${esc(dayTxt(x.day))}: ${x.risk}</title></rect>`).join("");
    const xAt = (day) => P.l + (r.days.findIndex((x) => x.day === day) + 0.5) * bw;
    const mark = (day, label, cls) => day === null || day === undefined || r.days.findIndex((x) => x.day === day) < 0 ? "" : `<line x1="${xAt(day)}" x2="${xAt(day)}" y1="${P.t}" y2="${H - P.b}" stroke="${cls}" stroke-dasharray="3 3"></line><text x="${xAt(day) + 3}" y="${P.t + 9}" font-size="10" fill="${cls}">${esc(label)}</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" role="img" aria-label="${L("Saathi priority score each day", "हर दिन साथी का प्राथमिकता स्कोर")}">
      <line x1="${P.l}" x2="${W - P.r}" y1="${Y(r.alert_at)}" y2="${Y(r.alert_at)}" stroke="var(--ink-3)" stroke-dasharray="4 4"></line><text x="${P.l - 4}" y="${Y(r.alert_at) + 4}" font-size="10" text-anchor="end" fill="var(--ink-3)">${r.alert_at}</text>
      <text x="${P.l - 4}" y="${Y(100) + 8}" font-size="10" text-anchor="end" fill="var(--ink-3)">100</text>${bars}
      ${upto >= r.days.findIndex((x) => x.day === r.decline_day) ? mark(r.decline_day, L("decline starts", "गिरावट शुरू"), "var(--ink-3)") : ""}
      ${r.alert_day !== null && upto >= r.days.findIndex((x) => x.day === r.alert_day) ? mark(r.alert_day, L("Saathi alerts", "साथी अलर्ट"), "var(--crit-ink)") : ""}
      <text x="${P.l}" y="${H - 5}" font-size="10" fill="var(--ink-3)">${esc(dayTxt(r.days[0].day))}</text><text x="${W - P.r}" y="${H - 5}" font-size="10" text-anchor="end" fill="var(--ink-3)">${L("emergency", "इमरजेंसी")}</text></svg>`;
  };
  const show = () => {
    const x = r.days[i];
    $("#rpGauge", d.el).innerHTML = Charts.gauge(x.risk, { color: VIZ[x.tier] || VIZ.GREEN, label: t("priority"), sub: `${t("priority")} · ${t("outOf")}` });
    $("#rpDay", d.el).textContent = dayTxt(x.day);
    const alerted = r.alert_day !== null && x.day >= r.alert_day;
    $("#rpBanner", d.el).innerHTML = alerted ? `<span class="badge crit">${ico("warn")}${L(`Saathi alerted the care manager ${r.lead_days} days before the emergency`, `साथी ने इमरजेंसी से ${r.lead_days} दिन पहले केयर मैनेजर को सचेत किया`)}</span>`
      : x.day >= r.decline_day ? `<span class="badge watch">${L("Something is starting to change", "कुछ बदलना शुरू हो रहा है")}</span>` : `<span class="badge ok">${L("A normal week", "सामान्य हफ़्ता")}</span>`;
    $("#rpChart", d.el).innerHTML = chart(i);
    const why = L(x.why_en, x.why_hi) || [];
    $("#rpToday", d.el).innerHTML = `<div class="tiles">
        <div class="tile"><div class="k">${ico("steps", "s")}${t("steps")}</div><div class="v">${x.steps === null || x.steps === undefined ? "–" : fmt(x.steps)}</div></div>
        <div class="tile"><div class="k">${ico("moon", "s")}${t("sleep")}</div><div class="v">${x.sleep ? fmt(x.sleep, 1) : "–"}<small>${L("h", "घं")}</small></div></div>
        <div class="tile"><div class="k">${ico("heart", "s")}${t("heart")}</div><div class="v">${x.hr ? fmt(x.hr) : "–"}<small>bpm</small></div></div>
        <div class="tile"><div class="k">${ico("pill", "s")}${L("Medicine", "दवा")}</div><div class="v">${x.meds ? L("taken", "ली") : L("missed", "छूटी")}</div></div></div>
      ${x.said ? `<p class="sm" style="margin-top:10px">${ico("mic", "s")} ${L("Said on the call", "कॉल में कहा")}: “${esc(x.said)}”</p>` : ""}
      ${why.length && x.risk > 0 ? `<ul class="sig-list">${why.map((w) => `<li>${ico("bulb", "s")}<span>${esc(w)}</span></li>`).join("")}</ul>` : ""}`;
    $("#rpSlide", d.el).value = i;
  };
  const stop = () => { clearInterval(timer); timer = null; $("#rpPlay", d.el).innerHTML = ico("chevR", "s"); };
  const play = () => { if (i >= maxI) i = 0; $("#rpPlay", d.el).innerHTML = ico("close", "s");
    timer = setInterval(() => { if (!document.body.contains(d.el)) return clearInterval(timer);
      i++; show(); if (i >= maxI) stop(); else if (r.days[i].day === r.alert_day) { stop(); setTimeout(() => { if (document.body.contains(d.el) && !timer) play(); }, 2200); } }, 750); };
  $("#rpPlay", d.el).onclick = () => (timer ? stop() : play());
  $("#rpSlide", d.el).oninput = (e) => { stop(); i = +e.target.value; show(); };
  d.onClose = () => clearInterval(timer);
  show(); play();
}

// ------------------------------------------------------------------------------------------ operations: Access log
const AUDIT = {
  en: { view_overview: "Viewed operations overview", view_summary: "Viewed family summary", view_senior: "Opened a person's record", ai_call: "Started a check-in call", login: "Signed in", login_failed: "Failed sign-in attempt",
        sos_confirmed: "Confirmed an emergency alert", sos_false_alarm: "Marked an alert as false alarm", sos_resolved: "Resolved an emergency alert",
        action_call_completed: "Follow-up: called them", action_nurse_dispatched: "Follow-up: sent a nurse or visit", action_med_reviewed: "Follow-up: reviewed medicines" },
  hi: { view_overview: "ऑपरेशन्स सारांश देखा", view_summary: "परिवार सारांश देखा", view_senior: "व्यक्ति का रिकॉर्ड खोला", ai_call: "चेक-इन कॉल शुरू की", login: "साइन इन किया", login_failed: "साइन इन की असफल कोशिश",
        sos_confirmed: "आपातकालीन अलर्ट की पुष्टि की", sos_false_alarm: "अलर्ट को झूठा अलार्म बताया", sos_resolved: "आपातकालीन अलर्ट सुलझाया",
        action_call_completed: "फ़ॉलो-अप: फ़ोन किया", action_nurse_dispatched: "फ़ॉलो-अप: नर्स / विज़िट भेजी", action_med_reviewed: "फ़ॉलो-अप: दवाओं की जाँच की" },
};
const auditLabel = (a) => (AUDIT[lang] && AUDIT[lang][a]) || AUDIT.en[a] || String(a || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const roleLabel = (r) => ({ coordinator: t("roleStaff"), ops: t("roleOps"), family: t("roleFamily") }[r] || r);
function drawAudit() {
  const page = $("#page"), rows = S.audit;
  if (!rows) { page.innerHTML = `<div class="card">${skeletonList(8)}</div>`; return; }
  page.innerHTML = `<div class="card"><div class="table-wrap"><table class="tbl cards-sm"><thead><tr><th>${t("when")}</th><th>${t("who")}</th><th>${t("did")}</th><th>${t("target")}</th></tr></thead>
    <tbody>${rows.map((a) => `<tr><td data-l="${t("when")}" title="${esc(fullTime(a.ts || a.time))}" class="subtle">${esc(rel(a.ts || a.time))}</td><td data-l="${t("who")}"><b>${esc(a.who)}</b> <span class="subtle">· ${esc(roleLabel(a.role))}</span></td><td data-l="${t("did")}">${esc(auditLabel(a.action))}</td><td data-l="${t("target")}" class="subtle">${esc(a.target || "–")}</td></tr>`).join("")}</tbody></table></div>
    ${rows.length ? "" : `<div class="empty">${ico("list", "xl")}<h3>${L("No activity yet", "अभी कोई गतिविधि नहीं")}</h3></div>`}</div>`;
}

// ------------------------------------------------------------------------------------------ boot
document.documentElement.lang = lang;
if (S.token && S.role) start(); else renderLogin();
})();
