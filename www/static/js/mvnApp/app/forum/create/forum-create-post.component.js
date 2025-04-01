function ForumCreatePostController($state, $rootScope, $scope, $window, Categories, Posts, ngNotify, ModalService, Plow, MvnStorage, config) {
	var vm = this,
		evt

	vm.btnTitle = "Post"
	vm.categorySelected = false
	vm.errorMsg = false
	vm.postForm = {
		anonymous: 0
	}
	vm.posting = false
	vm.started = false
	vm.subCats = []
	vm.selectedSubCats = {}

	// AMAs
	if ($state.params.community) {
		vm.postForm.categories = $state.params.community
		if ($state.params.ama) {
			vm.header = "Ask a question, share your story."
			vm.hideCommunity = true
		}
	}

	var storedPost = MvnStorage.getItem("session", "newPost")

	var checkUserName = function(post) {
		if (!post.anonymous) {
			if (vm.user.username || vm.user.role === "practitioner") {
				doCreatePost(post)
			} else {
				var onComplete = function(newU) {
					vm.user = newU
					doCreatePost(post)
				}
				ModalService.addUsername(vm.user, onComplete, true)
				vm.btnTitle = "Post"
				vm.posting = false
			}
		} else {
			doCreatePost(post)
		}
	}

	var doCreatePost = function(post) {
		const subCategories = Object.keys(vm.selectedSubCats).filter(function(sc) {
			return vm.selectedSubCats[sc]
		})
		post.categories = post.categories.concat(subCategories)

		Posts.createPost(post)
			.then(function(resp) {
				vm.errorMsg = false
				vm.posting = false
				evt = {
					event_name: "forum_submit_post",
					user_id: String(vm.user.id),
					anon: String(resp.anonymous),
					post_id: String(resp.id)
				}

				Plow.send(evt)

				$state.go(
					"app.forum.post-detail",
					{
						post_id: resp.id
					},
					{
						reload: true
					}
				)
				ngNotify.set("Success! You've just created a new post!", "success")
			})
			.catch(function(resp) {
				vm.errorMsg = true
				vm.posting = false
				vm.err = resp.data.message
			})
	}

	vm.addUsername = function() {
		var onComplete = function(newU) {
			vm.user = newU
			ngNotify.set("Added your username!", "success")
		}

		if (vm.user) {
			ModalService.addUsername(vm.user, onComplete, true)
		} else {
			ModalService.loginRegModal(onComplete)
		}
	}

	const goToLogin = () => {
		$window.location.href = "/login"
	}

	vm.createPost = function(post) {
		vm.btnTitle = "Please wait"
		vm.posting = true

		if (vm.marketplaceValidationComplete) { 
			// if they have already completed form validation then you don't have to check for the recaptcha response
			// or if they are an enterprise user or practitioner then don't check for the response
			if (vm.user) {
				checkUserName(post)
			} else {
				goToLogin()
			}
		} else {
			// you have to do the recaptcha validation
			if (Posts.checkRecaptchaResponse(vm.grecaptchaFullObject) === false) {
				vm.errorMsg = true
				vm.err = 'There was an error with proccessing checkbox validation'
				$scope.$apply()
			} else if (Posts.checkRecaptchaResponse(vm.grecaptchaFullObject) && vm.user) {
				// there was a response from recaptcha so you now have to send the token to the backend
				vm.postForm.recaptcha_token = vm.grecaptchaFullObject.enterprise.getResponse()
				checkUserName(post)
			} else {
				goToLogin()
			}
		}
	}

	vm.selectCategory = function(cat) {
		vm.categorySelected = true
		vm.selectedSubCats = {}
		Categories.getSubCats(cat).then(function(sc) {
			vm.subCats = sc
		})
	}

	function recaptchaClicked() {
		$scope.recaptchaStatus.clicked = true
		$scope.$apply()
	}

	var onloadCallback = () => {} // breaks when removing

	const formDefaultState = () => {
		$scope.recaptchaStatus = {
			clicked: true
		}
		vm.marketplaceValidationComplete = true
	}

	function prepareRecaptcha() {
		// Prepare recaptcha if it is not already ready
		// 1. Add the script tag to the page
		// 2. Call grecaptcha.ready to start tracking
		var reqForReplies = { "depth": 1, "author_ids": vm.user.id, "limit": 10, "offset": 0 };
		var allReplies = function() {
			Posts.getPosts()
			.getList(reqForReplies)
			.then(function(replies) {
				vm.totalReplies = replies.pagination.total
				var req = { "depth": 0, "author_ids": vm.user.id, "limit": 10, "offset": 0 };
				var allPosts = function() {
					Posts.getPosts()
					.getList(req)
					.then(function(posts) {
						vm.totalPosts = posts.pagination.total
						if (config.recaptcha_site_key !== "" && config.recaptcha_site_key) {
							if (vm.totalPosts < 1 && vm.totalReplies < 1 && Posts.checkUserType(vm.user)) {
								Posts.addRecaptchaScript(`https://www.google.com/recaptcha/enterprise.js?render=${config.recaptcha_site_key}onload=${onloadCallback}&render=explicit`, function() {
									$scope.recaptchaStatus = {
										clicked: false
									}
									vm.marketplaceValidationComplete = false
									setTimeout(() => {
										const grecaptcha = window.grecaptcha
										vm.grecaptchaFullObject = grecaptcha
										grecaptcha.enterprise.ready(function() { // updated to be the enterprise version
											$rootScope.recaptcha.ready = true;
											$rootScope.recaptcha.fullObject = grecaptcha;
											$rootScope.$digest()
										})
					
										grecaptcha.enterprise.render('g-recaptcha', { // have to use the render function in order to get access to the callback function for the click event on the input field
											callback: recaptchaClicked,
											"sitekey": config.recaptcha_site_key,
											"expired-callback": function() {
												$scope.recaptchaStatus.clicked = false
												$scope.$apply()
											},
											"error-callback": function() {
												$scope.recaptchaStatus.clicked = false
												$scope.$apply()
											}
										})
									}, 1000)
								})
							} else {
								formDefaultState()
							}
						} else {
							formDefaultState()
						}
					})
				}
				allPosts()
			})
		}
		allReplies()
	}

	vm.$onInit = function() {
		if (!vm.user) {
			// if they're not logged in, check if the user has sessionstorage available - for example, if in safari incognito, it's not. so we can't do our fancy post-after-login stuff.. so, we need to force our user to log in....
			if (typeof sessionStorage === "object") {
				try {
					sessionStorage.setItem("testStorage", "success")
					sessionStorage.removeItem("testStorage")
				} catch (e) {
					ModalService.loginRegModal()
				}
			}
		}

		prepareRecaptcha()

		// If we have a post stored in sessionStorage bc we've come from a post-auth redirect, populate the form and post it
		if (storedPost) {
			vm.postForm = JSON.parse(storedPost)
			MvnStorage.removeItem("session", "newPost")
			vm.createPost(vm.postForm)
		}
	}
}
angular.module("forum").component("forumCreatePost", {
	templateUrl: "/js/mvnApp/app/forum/create/index.html",
	controller: ForumCreatePostController,
	bindings: {
		user: "=",
		cats: "=",
		replies: "=",
		showSearchMenu: "="
	}
})
