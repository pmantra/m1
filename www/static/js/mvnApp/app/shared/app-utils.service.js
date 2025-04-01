angular.module("app").factory("AppUtils", [
	"deviceDetector",
	"Restangular",
	function(deviceDetector, Restangular) {
		return {
			videoCompatibleBrowser: (function() {
				var browserName = deviceDetector.browser,
					isMobile = deviceDetector.isMobile(),
					isTablet = deviceDetector.isTablet(),
					isDesktop = deviceDetector.isDesktop(),
					deviceOS = deviceDetector.os,
					isIE = browserName === "ie",
					desktopNotCompatible =
						isDesktop && browserName !== "firefox" && browserName !== "ie" && browserName !== "chrome",
					mobileNo = (isMobile && deviceOS !== "ios") || (deviceOS === "android" && browserName !== "chrome"),
					mobileMaybe = isMobile && deviceOS === "android" && browserName === "chrome", // Chrome on android supported but not tested...
					isIOS = deviceOS === "ios",
					isAndroid = deviceOS === "android"

				return {
					mayNotBeCompatible: desktopNotCompatible || isMobile,
					desktopNotCompatible: desktopNotCompatible,
					mobileNo: mobileNo,
					mobileMaybe: mobileMaybe,
					isIE: isIE,
					isIOS: isIOS,
					isAndroid: isAndroid,
					isMobileIos: isIOS && isMobile && !isTablet
				}
			})(),

			availableStates: [
				{
					code: "AL",
					name: "Alabama"
				},
				{
					code: "AK",
					name: "Alaska"
				},
				{
					code: "AR",
					name: "Arkansas"
				},
				{
					code: "AS",
					name: "American Samoa"
				},
				{
					code: "AZ",
					name: "Arizona"
				},
				{
					code: "CA",
					name: "California"
				},
				{
					code: "CO",
					name: "Colorado"
				},
				{
					code: "CT",
					name: "Connecticut"
				},
				{
					code: "DE",
					name: "Delaware"
				},
				{
					code: "DC",
					name: "District of Columbia"
				},

				{
					code: "FL",
					name: "Florida"
				},
				{
					code: "GA",
					name: "Georgia"
				},
				{
					code: "GU",
					name: "Guam"
				},
				{
					code: "HI",
					name: "Hawaii"
				},

				{
					code: "ID",
					name: "Idaho"
				},
				{
					code: "IL",
					name: "Illinois"
				},
				{
					code: "IN",
					name: "Indiana"
				},
				{
					code: "IA",
					name: "Iowa"
				},
				{
					code: "KS",
					name: "Kansas"
				},
				{
					code: "KY",
					name: "Kentucky"
				},
				{
					code: "LA",
					name: "Louisiana"
				},

				{
					code: "ME",
					name: "Maine"
				},
				{
					code: "MD",
					name: "Maryland"
				},
				{
					code: "MA",
					name: "Massachusetts"
				},

				{
					code: "MI",
					name: "Michigan"
				},
				{
					code: "MN",
					name: "Minnesota"
				},

				{
					code: "MS",
					name: "Mississippi"
				},
				{
					code: "MO",
					name: "Missouri"
				},
				{
					code: "MP",
					name: "Northern Mariana Islands"
				},
				{
					code: "MT",
					name: "Montana"
				},

				{
					code: "NE",
					name: "Nebraska"
				},
				{
					code: "NV",
					name: "Nevada"
				},
				{
					code: "NH",
					name: "New Hampshire"
				},
				{
					code: "NJ",
					name: "New Jersey"
				},
				{
					code: "NM",
					name: "New Mexico"
				},

				{
					code: "NY",
					name: "New York"
				},
				{
					code: "NC",
					name: "North Carolina"
				},
				{
					code: "ND",
					name: "North Dakota"
				},
				{
					code: "OH",
					name: "Ohio"
				},
				{
					code: "OK",
					name: "Oklahoma"
				},
				{
					code: "OR",
					name: "Oregon"
				},
				{
					code: "PA",
					name: "Pennsylvania"
				},
				{
					code: "PR",
					name: "Puerto Rico"
				},
				{
					code: "RI",
					name: "Rhode Island"
				},
				{
					code: "SC",
					name: "South Carolina"
				},
				{
					code: "SD",
					name: "South Dakota"
				},
				{
					code: "TN",
					name: "Tennessee"
				},
				{
					code: "TX",
					name: "Texas"
				},
				{
					code: "UM",
					name: "United States Minor Outlying Islands"
				},
				{
					code: "UT",
					name: "Utah"
				},
				{
					code: "VT",
					name: "Vermont"
				},
				{
					code: "VA",
					name: "Virginia"
				},
				{
					code: "VI",
					name: "Virgin Islands, U.S."
				},
				{
					code: "WA",
					name: "Washington"
				},
				{
					code: "WV",
					name: "West Virginia"
				},
				{
					code: "WI",
					name: "Wisconsin"
				},

				{
					code: "WY",
					name: "Wyoming"
				},
				{
					code: "ZZ",
					name: "International"
				}
			],

			pracNetworkTypes: [
				{
					type: "diamond",
					name: "Maven Diamond Network (telehealth with optional in-person referrals)"
				},
				{
					type: "platinum",
					name: "Maven Platinum Network (in-person referrals only)"
				}
			],

			removeTimeZone: date => {
				return moment(date)
					.startOf("day")
					.utc()
			},

			mergeDate: d => {
				return moment.utc([d.year, d.month - 1, d.day, 0, 0, 0]).format("YYYY-MM-DDTHH:mm:ss")
			},

			getCountries: () => {
				return Restangular.one("/_/geography").get()
			}
		}
	}
])
