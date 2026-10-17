export interface Messages {
  header: {
    service: string
    home: string
    nav: string
    rules: string
    api: string
    language: string
    openMenu: string
    closeMenu: string
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
  }
  upload: {
    title: string
    subtitle: string
    privacy: string
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
    subtitle: string
    subtitleFailed: string
    nowUploading: string
    nowAnalyzing: string
  }
  videoPreview: {
    caption: string
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
  }
  verdictSummary: {
    label: string
    violation: string
    clean: string
    checked: string
  }
  violationList: {
    hint: string
    whatWeLookFor: string
    rules: string
  }
  violationCard: {
    position: string
    prev: string
    next: string
    description: string
    rule: string
    adilet: string
    ruleUnknown: string
  }
  evidenceFrames: {
    frames: string
    frame: string
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
    subtitle: string
    colType: string
    colLooks: string
    colNorm: string
    colLink: string
    linkLabel: string
    noLink: string
    note: string
  }
  ruleNorm: {
    clause: string
    clausePending: string
  }
  textLink: {
    newTab: string
  }
  apiDocs: {
    title: string
    subtitle: string
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
    errorsTitle: string
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
  ruleLooks: {
    cashOutOfView: string
    outsider: string
    unattended: string
    countHidden: string
    personalItems: string
    phone: string
  }
  units: {
    b: string
    kb: string
    mb: string
    gb: string
  }
  batch: {
    title: string
    queueNote: string
    progress: string
    counts: string
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
  demo: {
    title: string
  }
}

declare const messages: Messages
export default messages
