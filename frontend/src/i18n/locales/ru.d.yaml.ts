export interface Messages {
  header: {
    home: string
    brand: string
    nav: string
    rules: string
    api: string
    language: string
    openMenu: string
    closeMenu: string
    demo: string
    history: string
  }
  titles: {
    upload: string
    processing: string
    violation: string
    clean: string
    rules: string
    api: string
    suffix: string
    batch: string
    history: string
  }
  upload: {
    title: string
  }
  dropZone: {
    region: string
    dropHere: string
    or: string
    choose: string
    chooseAnother: string
    hint: string
    release: string
    dropAgain: string
    formatTitle: string
    otherVideo: string
    otherFile: string
    noExtension: string
    emptyTitle: string
    emptyText: string
    tooManyTitle: string
    tooManyText: string
    noneValidTitle: string
    noneValidText: string
    noneValidEmptyText: string
  }
  processing: {
    title: string
    nowUploading: string
    nowAnalyzing: string
  }
  videoPreview: {
    alt: string
  }
  stepList: {
    list: string
    progress: string
    done: string
    active: string
    error: string
    pending: string
  }
  steps: {
    upload: string
    analysis: string
  }
  elapsedTimer: {
    running: string
    stopped: string
  }
  errorPanel: {
    title: string
    failed: string
    timeout: string
    network: string
    unauthorized: string
    notFound: string
    badFile: string
    server: string
    retry: string
    newVideo: string
  }
  report: {
    tabs: string
    report: string
    json: string
    newVideo: string
    selected: string
    backToList: string
    backToHistory: string
  }
  verdictSummary: {
    label: string
    violation: string
    clean: string
    checked: string
  }
  violationCard: {
    description: string
    rule: string
    requires: string
    check: string
    adilet: string
    ruleUnknown: string
  }
  evidenceFrames: {
    frames: string
    enlarge: string
  }
  frameLightbox: {
    frameOf: string
    alt: string
    close: string
    prev: string
    next: string
  }
  jsonView: {
    title: string
    note: string
    code: string
    copy: string
    copied: string
    copyFailed: string
    charsOne: string
    charsFew: string
    charsMany: string
    charsOther: string
  }
  player: {
    player: string
    play: string
    pause: string
    seek: string
    position: string
    speed: string
    fullscreen: string
    exitFullscreen: string
    marker: string
    markerGroup: string
    unavailable: string
    noSource: string
    cannotPlay: string
  }
  rules: {
    title: string
    colType: string
    colRequires: string
    colNorm: string
    check: string
    linkLabel: string
    documents: string
  }
  ruleNorm: {
    point: string
    sub: string
    article: string
    norm: string
    subItem: string
    subJoin: string
  }
  apiDocs: {
    title: string
    authTitle: string
    authText: string
    key: string
    headerLabel: string
    analyzeText: string
    requestExample: string
    response: string
    jobText: string
    jobPolling: string
    rulesLink: string
    jobResponse: string
    typesTitle: string
    typesText: string
    errorsTitle: string
    e400: string
    e401: string
    e404: string
    e422: string
  }
  codeBlock: {
    copy: string
    copied: string
    copyFailed: string
  }
  languages: {
    kk: string
    ru: string
    en: string
  }
  units: {
    b: string
    kb: string
    mb: string
    gb: string
  }
  batch: {
    title: string
    progress: string
    announceDone: string
    paused: string
    list: string
    rejectedTitle: string
    notMov: string
    empty: string
    startOver: string
    confirmStop: string
    confirmYes: string
    confirmNo: string
  }
  batchRow: {
    queued: string
    uploading: string
    analyzing: string
    open: string
    openLabel: string
    retryLabel: string
    progress: string
  }
  violationTypes: {
    cashLeftOut: string
    countWithoutClient: string
    mixedCash: string
    noRecount: string
    partialReturn: string
    rejectedNotes: string
    noId: string
    safeOpen: string
    keyLeft: string
    stampsLeft: string
    personalItems: string
    sessionUnlocked: string
    doorOpen: string
    notReady: string
    leftDuringService: string
    mobilePhone: string
  }
  review: {
    confirm: string
    reject: string
    confirmed: string
    rejected: string
    undo: string
    progress: string
    complete: string
  }
  act: {
    title: string
    number: string
    object: string
    file: string
    size: string
    duration: string
    hash: string
    job: string
    result: string
    reviewed: string
    pending: string
    violations: string
    colNumber: string
    colTime: string
    colType: string
    colRule: string
    colDecision: string
    noDecision: string
    frame: string
    signature: string
    downloadAct: string
    downloadJson: string
    documentName: string
    noHash: string
  }
  history: {
    title: string
    empty: string
    remove: string
    clear: string
    confirmClear: string
    confirmYes: string
    confirmNo: string
    fromHistory: string
    recheck: string
    missing: string
  }
  clip: {
    download: string
    recording: string
    failed: string
  }
  demo: {
    title: string
  }
  ruleRequires: {
    cashLeftOut: string
    countWithoutClient: string
    mixedCash: string
    noRecount: string
    partialReturn: string
    rejectedNotes: string
    noId: string
    safeOpen: string
    keyLeft: string
    stampsLeft: string
    personalItems: string
    sessionUnlocked: string
    doorOpen: string
    notReady: string
    leftDuringService: string
    mobilePhone: string
  }
  ruleCheck: {
    cashLeftOut: string
    countWithoutClient: string
    mixedCash: string
    noRecount: string
    partialReturn: string
    rejectedNotes: string
    noId: string
    safeOpen: string
    keyLeft: string
    stampsLeft: string
    personalItems: string
    sessionUnlocked: string
    doorOpen: string
    notReady: string
    leftDuringService: string
    mobilePhone: string
  }
  acts: {
    nbrk231: string
    nbrk14: string
    nbrk230: string
    ardfm53: string
    aml: string
  }
  actTitles: {
    nbrk231: string
    nbrk14: string
    nbrk230: string
    ardfm53: string
    aml: string
  }
  applicability: {
    direct: string
    conditional: string
    verify: string
    internal: string
    indirect: string
  }
}

declare const messages: Messages
export default messages
