document.documentElement.classList.add('has-js')

const copy = {
  zh: {
    meta: {
      title: 'GameForge | 产品展示',
      description: 'GameForge：用自然语言把游戏想法推进到可在浏览器试玩的版本。',
    },
    common: {
      skip: '跳到主要内容',
      navigation: '页面导航',
      language: '语言切换',
    },
    brand: { home: 'GameForge 首页' },
    nav: {
      flow: '产品链路',
      games: '开发游戏展示',
      product: '产品界面',
      project: '查看项目',
    },
    hero: {
      eyebrow: '浏览器游戏 AI 创作工作区',
      titleA: '把游戏想法',
      titleB: '推进到可试玩。',
      description: '描述规则，确认策划，生成浏览器游戏。无需离开工作区，就能打开、试玩、下载或提交发布。',
      primary: '查看开发游戏展示',
      secondary: '了解产品链路',
    },
    intro: {
      kicker: '是什么',
      title: '从一句玩法描述，走到一个可以打开的网页游戏。',
      bodyA: 'GameForge 是面向浏览器游戏的 AI 辅助创作工作区。它把创作过程组织为可审阅的策划、可追踪的生成任务和可直接打开的游戏版本。',
      bodyB: '从想法、策划到试玩和交付，创作者可以在一个工作区内完成关键步骤。',
    },
    flow: {
      eyebrow: '产品链路',
      title: '从创意输入到体验交付',
      description: '四个阶段串起六个关键动作，每一步都有明确输入、确认与产出。',
      phaseIdea: '创意输入',
      phasePlan: '策划确认',
      phaseBuild: '游戏生成',
      phaseDeliver: '体验交付',
      output: '阶段结果',
      step1: { title: '描述想法', body: '在 Forge 工作区用自然语言说明玩法、角色和规则。', output: '玩法描述' },
      step2: { title: 'AI 策划', body: '生成可查看的设计方案，将创作意图整理为游戏设计。', output: '策划方案' },
      step3: { title: '人工确认', body: '审阅设计方向；需要调整时回到策划，确认后再进入生成。', output: '已确认方案' },
      step4: { title: '生成游戏', body: '将设计转化为可运行的浏览器游戏，并实时反馈生成进度。', output: '可运行版本' },
      step5: { title: '浏览器试玩', body: '草稿或已发布版本均可直接打开，立即验证玩法与操作。', output: '试玩反馈' },
      step6: { title: '下载或发布', body: '下载独立 HTML 版本，或提交作品进入发布审核流程。', output: '可交付作品' },
    },
    features: {
      eyebrow: '产品能力',
      title: '从想法到交付，一处完成',
      item1: { title: '自然语言创作', body: '用自然语言开始一款浏览器游戏。' },
      item2: { title: '策划先行', body: '先确定玩法方向，再进入生成。' },
      item3: { title: '浏览器内试玩', body: '生成结果打开即玩，无需额外安装。' },
      item4: { title: '版本与发布管理', body: '保存、整理并分享你的游戏作品。' },
    },
    video: {
      eyebrow: '开发游戏展示',
      title: '完整展示',
      description: '看看不同玩法如何在浏览器中运行。',
      fallback: '当前浏览器不支持视频播放。',
      caption: '像素跑酷 · 塔防',
    },
    games: {
      eyebrow: '开发游戏展示',
      title: '试玩游戏展示',
      description: '从轻量跑酷到策略塔防，探索不同的创作方向。',
      runner: { tag: '跑酷', title: '像素跑酷', body: '霓虹重力跑酷。空格或点击反转重力，避开障碍并累计分数。' },
      defense: { tag: '塔防', title: '塔防雏形', body: '卡通塔防原型。选择并布置炮塔，阻击沿路径推进的敌人波次。' },
    },
    preview: {
      eyebrow: '产品体验',
      title: '产品体验',
      description: '从创作入口到游戏页面，关键体验一目了然。',
      home: { title: '首页', body: '发现与开始创作' },
      forge: { title: 'Forge 工作区', body: '描述想法与确认策划' },
      play: { title: '浏览器试玩', body: '打开游戏并开始体验' },
    },
    roadmap: {
      eyebrow: '接下来',
      title: '创作空间，持续扩展。',
      description: '更多工具与玩法正在加入 GameForge。',
      item1: '通过对话迭代已有游戏',
      item2: '上传自定义角色、背景与音效素材',
      item3: '更多游戏类型、模板与创作能力',
    },
    footer: { brand: 'GameForge · 浏览器游戏 AI 创作工作区', link: '项目说明' },
    media: {
      home: 'GameForge 产品首页',
      runner: '像素跑酷的动态游戏画面',
      defense: '塔防雏形的动态游戏画面',
      productHome: 'GameForge 首页',
      productForge: 'GameForge Forge 工作区',
      productGameplay: 'GameForge 浏览器试玩页',
    },
  },
  en: {
    meta: {
      title: 'GameForge | Product Showcase',
      description: 'GameForge: turn a game idea into a playable browser build with natural language.',
    },
    common: {
      skip: 'Skip to main content',
      navigation: 'Page navigation',
      language: 'Language switcher',
    },
    brand: { home: 'GameForge home' },
    nav: {
      flow: 'Product flow',
      games: 'Game showcase',
      product: 'Product interface',
      project: 'View project',
    },
    hero: {
      eyebrow: 'AI workspace for browser game creation',
      titleA: 'Turn game ideas',
      titleB: 'into playable builds.',
      description: 'Describe the rules, confirm the design, and generate a browser game. Open, play, download, or submit it without leaving the workspace.',
      primary: 'View game showcase',
      secondary: 'See product flow',
    },
    intro: {
      kicker: 'What it is',
      title: 'From one gameplay brief to a browser game you can open.',
      bodyA: 'GameForge is an AI-assisted workspace for browser games. It organizes creation into reviewable plans, traceable generation tasks, and game builds you can open directly.',
      bodyB: 'Creators can move from idea and planning to playtesting and delivery in one workspace.',
    },
    flow: {
      eyebrow: 'Product flow',
      title: 'From creative input to playable delivery',
      description: 'Four stages connect six key actions, each with a clear input, checkpoint, and output.',
      phaseIdea: 'Creative input',
      phasePlan: 'Plan & review',
      phaseBuild: 'Game build',
      phaseDeliver: 'Play & deliver',
      output: 'Stage output',
      step1: { title: 'Describe the idea', body: 'Use natural language in Forge to define gameplay, characters, and rules.', output: 'Gameplay brief' },
      step2: { title: 'AI planning', body: 'Turn the creative direction into a structured game design you can review.', output: 'Design plan' },
      step3: { title: 'Human review', body: 'Review the direction, adjust the plan when needed, then continue to generation.', output: 'Approved plan' },
      step4: { title: 'Generate the game', body: 'Turn the design into a runnable browser game with live progress feedback.', output: 'Runnable build' },
      step5: { title: 'Play in browser', body: 'Open a draft or published version to validate the gameplay and controls.', output: 'Playtest feedback' },
      step6: { title: 'Download or publish', body: 'Download an independent HTML build or submit the work for publishing review.', output: 'Deliverable game' },
    },
    features: {
      eyebrow: 'Capabilities',
      title: 'From idea to delivery, in one place',
      item1: { title: 'Natural-language creation', body: 'Start a browser game with a plain-language brief.' },
      item2: { title: 'Plan before build', body: 'Set the gameplay direction before generation begins.' },
      item3: { title: 'Play in browser', body: 'Open the generated result and play without extra installs.' },
      item4: { title: 'Version & publishing', body: 'Save, organize, and share your game work.' },
    },
    video: {
      eyebrow: 'Game showcase',
      title: 'Full walkthrough',
      description: 'See different gameplay directions running in the browser.',
      fallback: 'Your browser does not support video playback.',
      caption: 'Pixel runner · tower defense',
    },
    games: {
      eyebrow: 'Game showcase',
      title: 'Playable game showcase',
      description: 'Explore different creative directions, from light runner gameplay to strategic tower defense.',
      runner: { tag: 'Runner', title: 'Pixel Runner', body: 'Neon gravity runner. Press Space or click to reverse gravity, avoid obstacles, and build your score.' },
      defense: { tag: 'Tower defense', title: 'Tower Defense Prototype', body: 'A colorful tower defense prototype. Place turrets and stop enemy waves along the path.' },
    },
    preview: {
      eyebrow: 'Product experience',
      title: 'Product experience',
      description: 'See the key moments from the creation entry point to the playable game page.',
      home: { title: 'Home', body: 'Discover and start creating' },
      forge: { title: 'Forge workspace', body: 'Describe ideas and review plans' },
      play: { title: 'Browser playtest', body: 'Open the game and start playing' },
    },
    roadmap: {
      eyebrow: 'Next',
      title: 'A creative space that keeps expanding.',
      description: 'More tools and gameplay directions are coming to GameForge.',
      item1: 'Iterate on existing games through conversation',
      item2: 'Upload custom characters, backgrounds, and sound effects',
      item3: 'More genres, templates, and creation capabilities',
    },
    footer: { brand: 'GameForge · AI workspace for browser game creation', link: 'Project notes' },
    media: {
      home: 'GameForge product home',
      runner: 'Animated pixel runner gameplay',
      defense: 'Animated tower defense prototype gameplay',
      productHome: 'GameForge home',
      productForge: 'GameForge Forge workspace',
      productGameplay: 'GameForge browser playtest page',
    },
  },
}

const header = document.querySelector('[data-header]')
const revealItems = document.querySelectorAll('.reveal')
const languageButtons = document.querySelectorAll('[data-language]')

function getSavedLanguage() {
  const queryLanguage = new URLSearchParams(window.location.search).get('lang')
  if (queryLanguage === 'zh' || queryLanguage === 'en') return queryLanguage
  try {
    const savedLanguage = window.localStorage.getItem('gameforge-language')
    if (savedLanguage === 'zh' || savedLanguage === 'en') return savedLanguage
  } catch {
    // Storage may be unavailable when the page is opened from a restricted context.
  }
  return 'zh'
}

function getValue(language, path) {
  return path.split('.').reduce((value, key) => value?.[key], copy[language]) ?? ''
}

function applyLanguage(language) {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  document.documentElement.dataset.lang = language
  document.title = getValue(language, 'meta.title')

  document.querySelectorAll('[data-i18n]').forEach((element) => {
    element.textContent = getValue(language, element.dataset.i18n)
  })
  document.querySelectorAll('[data-i18n-content]').forEach((element) => {
    element.setAttribute('content', getValue(language, element.dataset.i18nContent))
  })
  document.querySelectorAll('[data-i18n-alt]').forEach((element) => {
    element.setAttribute('alt', getValue(language, element.dataset.i18nAlt))
  })
  document.querySelectorAll('[data-i18n-aria]').forEach((element) => {
    element.setAttribute('aria-label', getValue(language, element.dataset.i18nAria))
  })

  languageButtons.forEach((button) => {
    const isActive = button.dataset.language === language
    button.classList.toggle('is-active', isActive)
    button.setAttribute('aria-pressed', String(isActive))
  })

  try {
    window.localStorage.setItem('gameforge-language', language)
  } catch {
    // The page still works without persistent language preference.
  }

  const url = new URL(window.location.href)
  url.searchParams.set('lang', language)
  window.history.replaceState({}, '', url)
}

function updateHeader() {
  header?.classList.toggle('is-scrolled', window.scrollY > 16)
}

languageButtons.forEach((button) => {
  button.addEventListener('click', () => applyLanguage(button.dataset.language))
})

applyLanguage(getSavedLanguage())
updateHeader()
window.addEventListener('scroll', updateHeader, { passive: true })

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  revealItems.forEach((item) => item.classList.add('is-visible'))
} else {
  const observer = new IntersectionObserver(
    (entries, currentObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('is-visible')
        currentObserver.unobserve(entry.target)
      })
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
  )

  revealItems.forEach((item, index) => {
    item.style.transitionDelay = `${Math.min(index % 6, 4) * 55}ms`
    observer.observe(item)
  })
}
