/* eslint-disable */
// Chrome 53 / Android 6 stock WebView polyfill prelude.
// 必须在 React bundle 之前执行；用 IIFE 包，避免污染 globalThis 名字。
(function () {
  // ---- 视觉信标：prelude 跑就把背景染红，用户用眼睛能看见 ----
  try {
    var setRed = function () {
      if (document.body) document.body.style.background = "red";
      else setTimeout(setRed, 0);
    };
    setRed();
  } catch (_) { /* nothing */ }

  // ---- 网络信标：GET 不触发 CORS preflight，挂到 backend log 用 ----
  try {
    var img = new Image();
    img.src = "http://192.168.31.242:18000/api/v1/_debug/client-error-beacon?kind=PRELUDE_ALIVE&ts=" + Date.now();
  } catch (_) { /* nothing */ }

  // ---- globalThis ----
  if (typeof globalThis === "undefined") {
    if (typeof self !== "undefined") {
      // eslint-disable-next-line no-global-assign
      self.globalThis = self;
    } else if (typeof window !== "undefined") {
      window.globalThis = window;
    }
  }
  var G = typeof globalThis !== "undefined" ? globalThis : window;

  // ---- Object.fromEntries (Chrome 73) ----
  if (!Object.fromEntries) {
    Object.fromEntries = function (iter) {
      var obj = {};
      var arr = Array.isArray(iter) ? iter : Array.from(iter);
      for (var i = 0; i < arr.length; i++) {
        obj[arr[i][0]] = arr[i][1];
      }
      return obj;
    };
  }

  // ---- Object.hasOwn (Chrome 93) ----
  if (!Object.hasOwn) {
    Object.hasOwn = function (o, k) {
      return Object.prototype.hasOwnProperty.call(o, k);
    };
  }

  // ---- Array.prototype.flat / flatMap (Chrome 69) ----
  if (!Array.prototype.flat) {
    Array.prototype.flat = function (depth) {
      depth = depth === undefined ? 1 : depth;
      var out = [];
      (function rec(arr, d) {
        for (var i = 0; i < arr.length; i++) {
          var v = arr[i];
          if (Array.isArray(v) && d > 0) rec(v, d - 1);
          else out.push(v);
        }
      })(this, depth);
      return out;
    };
  }
  if (!Array.prototype.flatMap) {
    Array.prototype.flatMap = function (cb, thisArg) {
      return this.map(cb, thisArg).flat();
    };
  }

  // ---- Array.prototype.at / String.prototype.at (Chrome 92) ----
  if (!Array.prototype.at) {
    Array.prototype.at = function (i) {
      var n = i < 0 ? this.length + i : i;
      return this[n];
    };
  }
  if (!String.prototype.at) {
    String.prototype.at = function (i) {
      var n = i < 0 ? this.length + i : i;
      return this.charAt(n);
    };
  }

  // ---- String.prototype.replaceAll (Chrome 85) ----
  if (!String.prototype.replaceAll) {
    String.prototype.replaceAll = function (s, r) {
      if (Object.prototype.toString.call(s).toLowerCase() === "[object regexp]") {
        return this.replace(s, r);
      }
      return this.split(s).join(r);
    };
  }

  // ---- String.prototype.matchAll (Chrome 73) ----
  if (!String.prototype.matchAll) {
    String.prototype.matchAll = function (re) {
      if (!(re instanceof RegExp) || !re.global) {
        throw new TypeError("matchAll requires global RegExp");
      }
      var str = String(this);
      var out = [];
      var m;
      var lastIndex = re.lastIndex;
      re.lastIndex = 0;
      while ((m = re.exec(str)) !== null) {
        out.push(m);
        if (m.index === re.lastIndex) re.lastIndex++;
      }
      re.lastIndex = lastIndex;
      return out[Symbol.iterator] ? out[Symbol.iterator]() : out;
    };
  }

  // ---- Promise.allSettled (Chrome 76) ----
  if (typeof Promise !== "undefined" && !Promise.allSettled) {
    Promise.allSettled = function (promises) {
      return Promise.all(
        Array.prototype.map.call(promises, function (p) {
          return Promise.resolve(p).then(
            function (value) {
              return { status: "fulfilled", value: value };
            },
            function (reason) {
              return { status: "rejected", reason: reason };
            },
          );
        }),
      );
    };
  }

  // ---- Promise.any (Chrome 85) ----
  if (typeof Promise !== "undefined" && !Promise.any) {
    Promise.any = function (promises) {
      return new Promise(function (resolve, reject) {
        var errs = [];
        var rem = promises.length;
        if (rem === 0) {
          reject(new (G.AggregateError || Error)([], "All promises were rejected"));
          return;
        }
        promises.forEach(function (p, i) {
          Promise.resolve(p).then(resolve, function (e) {
            errs[i] = e;
            if (--rem === 0) {
              reject(new (G.AggregateError || Error)(errs, "All promises were rejected"));
            }
          });
        });
      });
    };
  }

  // ---- Numeric Number static (Chrome 47/52 mostly OK on 53 but safe) ----
  if (!Number.isFinite) Number.isFinite = function (n) { return typeof n === "number" && isFinite(n); };
  if (!Number.isNaN) Number.isNaN = function (n) { return n !== n; };

  // ---- structuredClone (Chrome 98) ----
  if (typeof structuredClone === "undefined") {
    G.structuredClone = function (v) {
      return JSON.parse(JSON.stringify(v));
    };
  }

  // ---- queueMicrotask (Chrome 71) ----
  if (typeof queueMicrotask === "undefined") {
    G.queueMicrotask = function (cb) {
      Promise.resolve().then(cb).catch(function (e) {
        setTimeout(function () { throw e; }, 0);
      });
    };
  }

  // ---- Error capture → 主动 POST 到 backend 便于诊断（Android stock WebView 没 console）----
  var reported = 0;
  function report(kind, msg, stack) {
    if (reported++ > 5) return; // 限流
    try {
      var url = (G.__BACKEND__ || "http://192.168.31.242:18000") + "/api/v1/_debug/client-error";
      var x = new XMLHttpRequest();
      x.open("POST", url, true);
      x.setRequestHeader("Content-Type", "application/json");
      x.send(JSON.stringify({
        kind: kind,
        message: String(msg).slice(0, 500),
        stack: String(stack || "").slice(0, 2000),
        ua: navigator.userAgent,
        url: location.href,
        ts: Date.now(),
      }));
    } catch (_) {
      /* ignore */
    }
  }
  G.addEventListener && G.addEventListener("error", function (e) {
    report("error", e.message || e.error || "unknown", e.error && e.error.stack);
  });
  G.addEventListener && G.addEventListener("unhandledrejection", function (e) {
    var r = e.reason || {};
    report("unhandledrejection", r.message || String(r), r.stack);
  });
})();
