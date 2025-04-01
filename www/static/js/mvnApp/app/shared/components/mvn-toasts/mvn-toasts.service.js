angular.module("app").factory("MvnToastService", function($rootScope, $compile, $timeout, ngNotify) {
	let toastVisible = false

	const setToast = opts => {
		// { title, content, type, duration, iconClass}
		let modalScope = $rootScope.$new(true)

		const defaultDuration = opts.type === "timed" ? 3500 : 800
		opts.duration = opts.duration || defaultDuration
		opts.content = opts.content || ""
		opts.delay = opts.delay || 0

		modalScope.self = modalScope // gotta store a reference to the scope here so we can properly clean it up in the directive and prevent memory leaks. Maybe there's a more elegant way of doing this.....
		modalScope.opts = opts

		modalScope.killToast = removeToast

		if (!toastVisible) renderToast(modalScope)

		let toastTimeout = () => {
			removeToast(modalScope)
		}

		if (opts.type === "timed") {
			var tm1 = $timeout(toastTimeout, opts.duration)
			var newPromise = tm1.then(() => $timeout.cancel(tm1)) // eslint-disable-line no-unused-vars
		}
	}

	const renderToast = theScope => {
		toastVisible = true
		let toastElement = $compile('<mvn-toast opts="opts" kill-toast="killToast(self)"></mvn-toast>')(theScope)

		_.delay(() => {
			angular.element(document.body).append(toastElement)
		}, theScope.opts.delay)
	}

	const removeToast = theScope => {
		let toastToRm = document.querySelector("mvn-toast")

		if (toastToRm) {
			document.body.removeChild(toastToRm)
			toastVisible = false
		}

		theScope.$destroy()
	}

	return {
		setToast: setToast,
		removeToast: removeToast
	}
})
