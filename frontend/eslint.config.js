import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strict,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      // 匹配 .eslintrc.json：以 _ 开头的参数/变量视为「有意未用」
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'no-console': 'warn',
      // eslint-plugin-react-hooks v5 新增；项目中有合法的 useEffect→setState 初始化模式
      // （URL→state、外部数据→form draft、debounce 重置）。降级为 warn，留待后续
      // useSyncExternalStore / useDeferredValue 重构。
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
])
