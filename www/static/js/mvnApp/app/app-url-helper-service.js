angular.module("app").factory("UrlHelperService", function() {
	const urldecode = encUrl => decodeURIComponent((encUrl + "").replace(/\+/g, "%20"))
	return {
		slug: function(str) {
			str = str.replace(/^\s+|\s+$/g, "") // trim
			str = str.toLowerCase()

			// remove accents, swap ñ for n, etc
			var from = "àáäâèéëêìíïîòóöôùúüûñç·/_,:;"
			var to = "aaaaeeeeiiiioooouuuunc------"
			for (var i = 0, l = from.length; i < l; i++) {
				str = str.replace(new RegExp(from.charAt(i), "g"), to.charAt(i))
			}

			str = str
				.replace(/[^a-z0-9 -]/g, "") // remove invalid chars
				.replace(/\s+/g, "-") // collapse whitespace and replace by -
				.replace(/-+/g, "-") // collapse dashes

			return str
		},
		deslug: function(str) {
			str = str.replace("-", " ")
			return str
		},

		urlencode: function(str) {
			return encodeURIComponent(str)
				.replace(/!/g, "%21")
				.replace(/'/g, "%27")
				.replace(/\(/g, "%28")
				.replace(/\)/g, "%29")
				.replace(/\*/g, "%2A")
				.replace(/%20/g, "+")
		},

		urldecode,

		// modified https://css-tricks.com/snippets/javascript/get-url-variables/
		getParamValue: function(fullUrl, variable) {
			var query = fullUrl.split("?")[1],
				vars
			if (query) {
				vars = query.split("&")
				for (var i = 0; i < vars.length; i++) {
					var pair = vars[i].split("=")
					if (pair[0] == variable) {
						return pair[1]
					}
				}
				return false
			} else {
				return false
			}
		},

		// modified version of https://stackoverflow.com/a/1917916
		appendParam: function(thePath, key, value) {
			key = encodeURIComponent(key)
			value = encodeURIComponent(value)

			var baseUrl = thePath.split("?")[0]

			if (thePath.split("?")[1]) {
				var allParams = thePath.split("?")[1],
					x,
					kvp = allParams.split("&")

				var i = kvp.length

				while (i--) {
					x = kvp[i].split("=")

					if (x[0] == key) {
						x[1] = value
						kvp[i] = x.join("=")
						break
					}
				}
				if (i < 0) {
					kvp[kvp.length] = [key, value].join("=")
				}
				thePath = kvp.join("&")
			} else {
				thePath = key + "=" + value
			}

			return baseUrl + "?" + thePath
		},

		// https://stackoverflow.com/a/8649003
		convertParamsToObj: function(paramList) {
			return JSON.parse('{"' + paramList.replace(/&/g, '","').replace(/=/g, '":"') + '"}', function(key, value) {
				return key === "" ? value : decodeURIComponent(value)
			})
		},

		isValidFromPath: from => {
			const fromUrl = urldecode(from)

			const getHostnameFromRegex = url => {
				// run against regex
				// eslint-disable-next-line
				const matches = url.match(/^https?\:\/\/([^\/?#]+)(?:[\/?#]|$)/i)
				// extract hostname (will be null if no match is found)
				return matches && matches[1]
			}

			// starts with forward slash, followed by alphanumeric and any of ?,/,&,-,_,=, ,
			// eslint-disable-next-line
			const isRelative = url => url.match(/^\/[\?\=\_,\&a-z0-9\/-]+$/i)

			// if the from path either starts with "/" (so is relative) or the host matches, we can assume this is valid.
			if (isRelative(fromUrl) || getHostnameFromRegex(fromUrl) === document.location.host) {
				return fromUrl
			}
		},

		redirectToReact: function (reactPath) {
			if (window.location.host === "localhost:3030") {
				window.location.assign(`https://www.mvnctl.net:3000${reactPath}`)
			} else {
				window.location.assign(reactPath)
			}
		}
	}
})
