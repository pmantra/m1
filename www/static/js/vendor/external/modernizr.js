/*! modernizr 3.6.0 (Custom Build) | MIT *
 * https://modernizr.com/download/?-formvalidation-inputtypes-localstorage-sessionstorage-video-setclasses !*/

/*
Custom MVN modernizr build based on json at /mvn-modernizr.config.json
We use/update this infrequently so not making generating this part of the build process.
To add new Modernizr features, update mvn-modernizr-config.json (see https://modernizr.com/docs)
then run:

`node_modules/modernizr/bin/modernizr -c mvn-modernizr-config.json`

this will create a new modernizr.js file in the /www folder.
Which is icky.
So grab the contents and paste below... then delete the modernizr.js file from /www .
(which is also icky but come fight me brah)
 */

!(function(e, t, n) {
	function a(e, t) {
		return typeof e === t;
	}
	function o() {
		var e, t, n, o, i, r, s;
		for (var l in d)
			if (d.hasOwnProperty(l)) {
				if (
					((e = []),
					(t = d[l]),
					t.name &&
						(e.push(t.name.toLowerCase()),
						t.options && t.options.aliases && t.options.aliases.length))
				)
					for (n = 0; n < t.options.aliases.length; n++)
						e.push(t.options.aliases[n].toLowerCase());
				for (o = a(t.fn, "function") ? t.fn() : t.fn, i = 0; i < e.length; i++)
					(r = e[i]),
						(s = r.split(".")),
						1 === s.length
							? (Modernizr[s[0]] = o)
							: (!Modernizr[s[0]] ||
									Modernizr[s[0]] instanceof Boolean ||
									(Modernizr[s[0]] = new Boolean(Modernizr[s[0]])),
							  (Modernizr[s[0]][s[1]] = o)),
						p.push((o ? "" : "no-") + s.join("-"));
			}
	}
	function i(e) {
		var t = u.className,
			n = Modernizr._config.classPrefix || "";
		if ((f && (t = t.baseVal), Modernizr._config.enableJSClass)) {
			var a = new RegExp("(^|\\s)" + n + "no-js(\\s|$)");
			t = t.replace(a, "$1" + n + "js$2");
		}
		Modernizr._config.enableClasses &&
			((t += " " + n + e.join(" " + n)),
			f ? (u.className.baseVal = t) : (u.className = t));
	}
	function r() {
		return "function" != typeof t.createElement
			? t.createElement(arguments[0])
			: f
				? t.createElementNS.call(t, "http://www.w3.org/2000/svg", arguments[0])
				: t.createElement.apply(t, arguments);
	}
	function s() {
		var e = t.body;
		return e || ((e = r(f ? "svg" : "body")), (e.fake = !0)), e;
	}
	function l(e, n, a, o) {
		var i,
			l,
			d,
			c,
			p = "modernizr",
			f = r("div"),
			m = s();
		if (parseInt(a, 10))
			for (; a--; )
				(d = r("div")), (d.id = o ? o[a] : p + (a + 1)), f.appendChild(d);
		return (
			(i = r("style")),
			(i.type = "text/css"),
			(i.id = "s" + p),
			(m.fake ? m : f).appendChild(i),
			m.appendChild(f),
			i.styleSheet
				? (i.styleSheet.cssText = e)
				: i.appendChild(t.createTextNode(e)),
			(f.id = p),
			m.fake &&
				((m.style.background = ""),
				(m.style.overflow = "hidden"),
				(c = u.style.overflow),
				(u.style.overflow = "hidden"),
				u.appendChild(m)),
			(l = n(f, e)),
			m.fake
				? (m.parentNode.removeChild(m), (u.style.overflow = c), u.offsetHeight)
				: f.parentNode.removeChild(f),
			!!l
		);
	}
	var d = [],
		c = {
			_version: "3.6.0",
			_config: {
				classPrefix: "",
				enableClasses: !0,
				enableJSClass: !0,
				usePrefixes: !0
			},
			_q: [],
			on: function(e, t) {
				var n = this;
				setTimeout(function() {
					t(n[e]);
				}, 0);
			},
			addTest: function(e, t, n) {
				d.push({ name: e, fn: t, options: n });
			},
			addAsyncTest: function(e) {
				d.push({ name: null, fn: e });
			}
		},
		Modernizr = function() {};
	(Modernizr.prototype = c), (Modernizr = new Modernizr());
	var p = [],
		u = t.documentElement,
		f = "svg" === u.nodeName.toLowerCase();
	Modernizr.addTest("video", function() {
		var e = r("video"),
			t = !1;
		try {
			(t = !!e.canPlayType),
				t &&
					((t = new Boolean(t)),
					(t.ogg = e
						.canPlayType('video/ogg; codecs="theora"')
						.replace(/^no$/, "")),
					(t.h264 = e
						.canPlayType('video/mp4; codecs="avc1.42E01E"')
						.replace(/^no$/, "")),
					(t.webm = e
						.canPlayType('video/webm; codecs="vp8, vorbis"')
						.replace(/^no$/, "")),
					(t.vp9 = e
						.canPlayType('video/webm; codecs="vp9"')
						.replace(/^no$/, "")),
					(t.hls = e
						.canPlayType('application/x-mpegURL; codecs="avc1.42E01E"')
						.replace(/^no$/, "")));
		} catch (n) {}
		return t;
	});
	var m = (c.testStyles = l);
	Modernizr.addTest("formvalidation", function() {
		var t = r("form");
		if (!("checkValidity" in t && "addEventListener" in t)) return !1;
		if ("reportValidity" in t) return !0;
		var n,
			a = !1;
		return (
			(Modernizr.formvalidationapi = !0),
			t.addEventListener(
				"submit",
				function(t) {
					(!e.opera || e.operamini) && t.preventDefault(), t.stopPropagation();
				},
				!1
			),
			(t.innerHTML =
				'<input name="modTest" required="required" /><button></button>'),
			m("#modernizr form{position:absolute;top:-99999em}", function(e) {
				e.appendChild(t),
					(n = t.getElementsByTagName("input")[0]),
					n.addEventListener(
						"invalid",
						function(e) {
							(a = !0), e.preventDefault(), e.stopPropagation();
						},
						!1
					),
					(Modernizr.formvalidationmessage = !!n.validationMessage),
					t.getElementsByTagName("button")[0].click();
			}),
			a
		);
	});
	var v = r("input"),
		y = "search tel url email datetime date month week time datetime-local number range color".split(
			" "
		),
		g = {};
	(Modernizr.inputtypes = (function(e) {
		for (var a, o, i, r = e.length, s = "1)", l = 0; r > l; l++)
			v.setAttribute("type", (a = e[l])),
				(i = "text" !== v.type && "style" in v),
				i &&
					((v.value = s),
					(v.style.cssText = "position:absolute;visibility:hidden;"),
					/^range$/.test(a) && v.style.WebkitAppearance !== n
						? (u.appendChild(v),
						  (o = t.defaultView),
						  (i =
								o.getComputedStyle &&
								"textfield" !== o.getComputedStyle(v, null).WebkitAppearance &&
								0 !== v.offsetHeight),
						  u.removeChild(v))
						: /^(search|tel)$/.test(a) ||
						  (i = /^(url|email)$/.test(a)
								? v.checkValidity && v.checkValidity() === !1
								: v.value != s)),
				(g[e[l]] = !!i);
		return g;
	})(y)),
		Modernizr.addTest("localstorage", function() {
			var e = "modernizr";
			try {
				return localStorage.setItem(e, e), localStorage.removeItem(e), !0;
			} catch (t) {
				return !1;
			}
		}),
		Modernizr.addTest("sessionstorage", function() {
			var e = "modernizr";
			try {
				return sessionStorage.setItem(e, e), sessionStorage.removeItem(e), !0;
			} catch (t) {
				return !1;
			}
		}),
		o(),
		i(p),
		delete c.addTest,
		delete c.addAsyncTest;
	for (var h = 0; h < Modernizr._q.length; h++) Modernizr._q[h]();
	e.Modernizr = Modernizr;
})(window, document);
