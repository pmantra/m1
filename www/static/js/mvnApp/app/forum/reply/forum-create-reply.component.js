function ForumCreateReplyController($rootScope, $state, $scope, $window, ngNotify, Plow, Posts, ModalService, MvnStorage, config) {
	var vm = this

	var storedReply = MvnStorage.getItem("session", "postReply")

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

	var postReply = function (replyForm) {
		vm.replyForm.isDisabled = true;
		Posts.createPost(replyForm)
			.then(function(post) {
				vm.errorMsg = false
				ngNotify.set("Reply posted!", "success")
				
				var evt = {
					event_name: "forum_submit_reply",
					user_id: String(vm.user.id),
					anon: String(post.anonymous),
					reply_length: String(post.body.length),
					post_id: String(post.id)
				}
				Plow.send(evt)
				
				vm.replyForm = {
					parent_id: vm.post.id,
					anonymous: false,
					isDisabled: false
				}
				vm.replies.push(post)
				vm.replies.pagination.total++
				vm.authorType = post.author ? post.author.role : "member"
				
				// if the recaptcha was present then hide if
				var grecaptchaElement = document.getElementById('g-recaptcha');
				if (grecaptchaElement) {
					grecaptchaElement.style.visibility = "hidden";
					// change the default form validation
					formDefaultState()
				}
			})
			.catch(function(resp) {
				vm.errorMsg = true
				vm.err = resp.data.message
				vm.replyForm = {
					isDisabled: false
				}
			})
	}

	var checkUserName = function(post) {
		if (!post.anonymous) {
			if (vm.user.username || vm.user.role === "practitioner") {
				postReply(post)
			} else {
				var onComplete = function(newU) {
					vm.user = newU
					postReply(post)
				}
				ModalService.addUsername(vm.user, onComplete)
			}
		} else {
			postReply(post)
		}
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

	vm.reply = function(reply) {
		// there needs to be a usecase for user is a marketplace user but they don't need to have the recaptcha information, because they have already been validated
		if (vm.marketplaceValidationComplete) {
			// if they have already completed form validation then you don't have to check for the recaptcha response
			if (vm.user) {
				checkUserName(reply)
			} else {
				goToLogin()
			}
		} else {
			// you have to do the recaptcha validation
			if (Posts.checkRecaptchaResponse(vm.grecaptchaFullObject) === false) { // checks for the response back from recaptcha
				vm.errorMsg = true
				vm.err = 'There was an error with proccessing checkbox validation'
				$scope.$apply()
			} else if (Posts.checkRecaptchaResponse(vm.grecaptchaFullObject) && vm.user) { // checks for user type (marketplace or enterprise)
				// also add on the verification token for the checkbox item
				vm.replyForm.recaptcha_token = vm.grecaptchaFullObject.enterprise.getResponse()
				checkUserName(reply)
			} else {
				goToLogin()
			}
		}
	}

	vm.$onInit = function() {
		if (!vm.user) {
			// if they're not logged in, check if the user has sessionstorage available - for example, if in safari incognito, it's not. so we can't do our fancy post-after-login stuff.. so, we need to force our user to log in....
			if (typeof sessionStorage === "object") {
				try {
					sessionStorage.setItem("testStorage", "success")
					sessionStorage.removeItem("testStorage")
				} catch (e) {
					vm.hideReplyForm = true
				}
			}
		}
		
		prepareRecaptcha()

		vm.loading = true
		vm.replyForm = {
			parent_id: vm.post.id,
			anonymous: false,
			isDisabled: false
		}

		// If we have a reply stored in sessionStorage bc we've come from a post-auth redirect, populate the form and post it
		if (storedReply) {
			vm.postForm = JSON.parse(storedReply)
			MvnStorage.removeItem("session", "postReply")
			vm.reply(vm.postForm)
		}
	}
}

angular.module("forum").component("forumCreateReply", {
	templateUrl: "/js/mvnApp/app/forum/reply/_create-reply.html",
	controller: ForumCreateReplyController,
	bindings: {
		user: "=",
		post: "<",
		replies: "="
	}
})
