// Sprint 14.3 — 公开 App 下载与使用指南页 (PRD §8.2)
// 公开路由：所有人（含未登录）可见
import {
  ArrowLeft,
  Download,
  Headphones,
  KeyRound,
  Settings as SettingsIcon,
  Smartphone,
} from "lucide-react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

function goBackOrHome() {
  if (window.history.length > 1) {
    window.history.back();
  } else {
    window.location.href = "/";
  }
}

interface AppInfo {
  apk_url: string;
  apk_version: string;
  min_android_version: string;
  download_size_mb: number;
  notes: string;
}

export function HelpAppPage() {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/public/app-info`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => setAppInfo(d as AppInfo))
      .catch(() => setLoadError(true));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <button
          type="button"
          onClick={goBackOrHome}
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600"
        >
          <ArrowLeft className="w-4 h-4" /> 返回
        </button>
        <header className="text-center">
          <div className="inline-flex items-center gap-2 mb-2">
            <Smartphone className="w-7 h-7 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">手机 App 安装与使用</h1>
          </div>
          <p className="text-sm text-gray-600">
            外呼必须使用 Android App。本页面公开访问，可分享给坐席。
          </p>
        </header>

        {/* QR + Download */}
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row gap-6">
            <div className="flex-shrink-0 flex flex-col items-center">
              {appInfo ? (
                <>
                  <QRCodeSVG value={appInfo.apk_url} size={200} />
                  <a
                    href={appInfo.apk_url}
                    className="mt-3 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                  >
                    <Download className="w-4 h-4" /> 直接下载 APK
                  </a>
                </>
              ) : loadError ? (
                <div className="w-[200px] h-[200px] flex items-center justify-center text-sm text-red-600 border border-red-200 rounded">
                  加载下载链接失败
                </div>
              ) : (
                <div className="w-[200px] h-[200px] flex items-center justify-center text-sm text-gray-400 border border-gray-200 rounded">
                  加载中…
                </div>
              )}
            </div>
            <div className="flex-1 space-y-3 text-sm">
              <div>
                <div className="text-xs text-gray-500 mb-1">当前版本</div>
                <div className="font-mono text-gray-900">{appInfo?.apk_version ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">最低系统要求</div>
                <div>{appInfo?.min_android_version ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">安装包大小</div>
                <div>{appInfo ? `${appInfo.download_size_mb} MB` : "—"}</div>
              </div>
              <p className="text-xs text-gray-500 pt-2">
                用 Android 手机自带浏览器扫码即可下载 APK。
                如系统提示「未知来源」，请到设置中允许此次安装。
              </p>
            </div>
          </div>
        </section>

        <Section icon={<Headphones className="w-5 h-5" />} title="为什么需要 App">
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
            <li>外呼电话必须通过手机系统拨号器发起，PC 无法直接打电话</li>
            <li>App 自动采集系统通话录音、上传后端做 ASR + AI 分析</li>
            <li>App 内拨号会同步推送给 PC 主管/管理员的「实时通话墙」</li>
            <li>支持扫码拨号备份方案（PC 生成二维码 → App 扫码即可拨号）</li>
          </ul>
        </Section>

        <Section icon={<Download className="w-5 h-5" />} title="安装步骤">
          <ol className="list-decimal list-inside space-y-1 text-sm text-gray-700">
            <li>用手机浏览器扫描上方二维码</li>
            <li>点「下载」→ 完成后在通知栏点击 APK</li>
            <li>系统弹「未知来源」→ 设置中开启「允许此次安装」</li>
            <li>安装完成 → 桌面打开「autoluyin 测试」</li>
          </ol>
        </Section>

        <Section icon={<KeyRound className="w-5 h-5" />} title="权限授予（一次性）">
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
            <li>电话 / 通话状态 / 通话记录 — 监听拨号事件</li>
            <li>通知 — 显示后台采集状态</li>
            <li>相机 — 扫码拨号功能</li>
            <li>读取媒体音频 — 上传系统通话录音</li>
            <li>
              <strong>MIUI 设备额外</strong>：「所有文件访问权限」必须开启，
              否则 App 无法读取
              <code className="bg-gray-100 px-1 rounded mx-1">
                /storage/emulated/0/MIUI/sound_recorder/call_rec/
              </code>
              下的录音文件
            </li>
          </ul>
        </Section>

        <Section icon={<SettingsIcon className="w-5 h-5" />} title="服务器地址配置">
          <p className="text-sm text-gray-700 mb-2">
            首次打开 App 会要求输入后端服务器地址：
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
            <li>
              手动输入：管理员告知的形如
              <code className="bg-gray-100 px-1 rounded mx-1">
                https://api.your-domain.com
              </code>
              的地址
            </li>
            <li>
              扫码注入：管理员可生成包含服务器地址的二维码，App 扫描后自动填入（避免手输出错）
            </li>
          </ul>
        </Section>
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3 text-gray-900">
        {icon}
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}
