/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        /**
         * 品牌色 · Electric Blue。
         * 色阶的两个锚点直接取自设计系统的渐变端点：
         *   600 = #0052FF（accent，主色）  400 = #4D7CFF（accent-secondary，渐变终点）
         * 这样「单色阶 + 单色渐变」自洽：btn/card 的渐变就是 from-brand-600 to-brand-400，
         * 不需要再引入第二个色相（旧方案是靛蓝 + 紫色双色相）。
         */
        brand: {
          50: '#EFF5FF',
          100: '#DBE8FF',
          200: '#BFD6FF',
          300: '#93BAFF',
          400: '#4D7CFF',
          500: '#1F63FF',
          600: '#0052FF',
          700: '#0043D6',
          800: '#0736A8',
          900: '#0B2F80',
        },
        // 语义色：业务状态（绿=达成 / 黄=预警 / 红=异常），与品牌色相互独立
        good: { 50: '#ECFDF5', 100: '#D1FAE5', 500: '#10B981', 600: '#059669', 700: '#047857' },
        warn: { 50: '#FFFBEB', 100: '#FEF3C7', 500: '#F59E0B', 600: '#D97706', 700: '#B45309' },
        bad: { 50: '#FEF2F2', 100: '#FEE2E2', 500: '#EF4444', 600: '#DC2626', 700: '#B91C1C' },
      },
      fontFamily: {
        /**
         * 纯系统字体栈：不引用任何外部字体，避免渲染阻塞与国内网络不可达。
         * 中西文分工由浏览器逐字回退完成（拉丁数字走 -apple-system/Segoe UI，中文走 PingFang SC/微软雅黑）。
         *
         * 设计系统原本的三套字体（Calistoga / Inter / JetBrains Mono）在此约束下这样落地：
         *   · Calistoga（衬线显示体，且不含中文）→ 用「特粗字重 + 紧字距」表达标题的个性；
         *   · Inter（正文）→ 系统无衬线；
         *   · JetBrains Mono（技术感徽章/编号）→ 系统等宽栈（下方 mono），
         *     既保留技术感，又让任务 ID、指标数值获得等宽对齐的可用性收益。
         */
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'PingFang SC',
          'Microsoft YaHei',
          'Segoe UI',
          'Helvetica Neue',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'SF Mono',
          'Menlo',
          'Consolas',
          'Liberation Mono',
          'monospace',
        ],
      },
      letterSpacing: {
        /** 设计系统的标题字距 -0.02em，比 Tailwind 默认 tighter 更克制 */
        display: '-0.02em',
      },
      boxShadow: {
        // 彩色阴影：全部带品牌蓝调，替代中性灰（设计系统的标志性特征）
        card: '0 4px 20px -2px rgba(0, 82, 255, 0.10)',
        cardHover: '0 10px 25px -5px rgba(0, 82, 255, 0.15), 0 8px 10px -6px rgba(0, 82, 255, 0.10)',
        btn: '0 4px 14px 0 rgba(0, 82, 255, 0.30)',
        btnHover: '0 8px 24px rgba(0, 82, 255, 0.35)',
        glow: '0 0 20px rgba(0, 82, 255, 0.50)',
        pop: '0 20px 40px -12px rgba(15, 23, 42, 0.18)',
      },
      borderRadius: { xl2: '16px' },
      maxWidth: { content: '1440px' },
      keyframes: {
        /** 登录页装饰卡片的缓慢浮动（设计系统的「会呼吸的界面」） */
        float: {
          '0%, 100%': { transform: 'translateY(-6px)' },
          '50%': { transform: 'translateY(6px)' },
        },
        /** 极慢旋转（装饰环），60s 一圈，几乎察觉不到但让画面"活着" */
        spinSlow: { to: { transform: 'rotate(360deg)' } },
        /** 脉冲指示点：给「在线/实时」一类标签用 */
        pulseDot: {
          '0%, 100%': { transform: 'scale(1)', opacity: '1' },
          '50%': { transform: 'scale(1.3)', opacity: '0.7' },
        },
      },
      animation: {
        float: 'float 5s ease-in-out infinite',
        'float-slow': 'float 7s ease-in-out infinite',
        'spin-slow': 'spinSlow 60s linear infinite',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
