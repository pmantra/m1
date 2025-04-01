angular.module("publicpages").controller("CaseStudyCtrl", [
	"$scope",
	"ngDialog",
	"MvnStorage",
	function($scope, ngDialog, MvnStorage) {
		const installParams = MvnStorage.getItem("local", "mvnInst")
			? JSON.parse(MvnStorage.getItem("local", "mvnInst"))
			: null
		const installAttrs = installParams || {}

		$scope.openDemoRequest = function() {
			ngDialog.open({
				template: "/js/mvnApp/public/enterprise/_enterprise-contact.html",
				className: "mvndialog",
				scope: true,
				controller: [
					"$scope",
					function($scope) {
						$scope.instParams = installAttrs
					}
				]
			})
		}

		$scope.slickDots = function(slider, i) {
			return "<span></span>"
		}

		$scope.csCarouselBreakpoints = [
			{
				breakpoint: 768,
				settings: {
					slidesToShow: 1,
					slidesToScroll: 1
				}
			},
			{
				breakpoint: 1220,
				settings: {
					slidesToShow: 2,
					slidesToScroll: 2
				}
			}
		]

		// Snap Inc
		$scope.snapTestimonials = [
			{
				category: "employee",
				quote: `I met with my OB-GYN today and I always feel rushed there. I feel bad asking my questions! So glad to know that I have Maven's support.`,
				by: "Snap Inc. Employee"
			},
			{
				category: "employee",
				quote: `Liz (Maven coach) was so sweet and easy to talk to. I loved meeting with her. She made me feel much better about where I am in my life with life and all the crazy transitions!`,
				by: "Snap Inc. Employee"
			},
			{
				category: "employee",
				quote: `This is an exceptional benefit—so happy to see Snap Inc. doing this! Women’s health is so underfunded and under-supported out in the world and I love that my company is providing me financial assistance and other resources to achieve my ultimate goal of becoming a mom.`,
				by: "Snap Inc. Employee"
			}
		]

		$scope.clearyTestimonials = [
			{
				category: "employee",
				quote: `Maven is by far one of the best benefits within the benefits package. Again, a great offering!!!`,
				by: "CLEARY GOTTLIEB EMPLOYEE"
			},
			{
				category: "employee",
				quote: `My Maven Care Advocate was great. She really understood my issues at this early phase of my pregnancy and helped me understand what resources are there to help. I'm looking forward to working with her for the next nine months.`,
				by: "CLEARY GOTTLIEB EMPLOYEE"
			},
			{
				category: "employee",
				quote: `I just wanted to give a great big “thumbs-up” for making accessible such important and vital information for the people who need it.`,
				by: "CLEARY GOTTLIEB EMPLOYEE"
			}
		]
	}
])
