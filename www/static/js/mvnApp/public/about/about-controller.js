/**
 * @ngdoc function
 * @name public.controller:AboutCtrl
 * @description
 * # AboutCtrl
 * Controller of the public
 */
angular.module('publicpages')
	.controller('AboutCtrl', ["$scope", "ModalService", function ($scope, ModalService) {

		$scope.people = [{
				name: "Katherine Ryder",
				title: "Founder & CEO",
				imgclass: "kate",
				bio: `<p>Before launching Maven, Katherine worked as an early stage investor at the venture capital firm Index Ventures, based in London, where she focused on consumer technology and investments in the health, education, art, and retail sectors. </p>

					<p>Prior to joining Index, Katherine was a journalist for The Economist from Southeast Asia, New York, and London. In 2009, she helped former U.S. Treasury Secretary Hank Paulson write his memoirs about the U.S. financial crisis. </p>

					<p>Katherine received her B.A. from the Honors College at the University of Michigan and her MSc from the London School of Economics. </p>

					<p>Now a mother of two, Katherine uses Maven on the regular and continues to expand offerings to support all women at every stage of life.</p>`
			},
			{
				name: "Thomas Barone",
				title: "VP of Growth",
				imgclass: "tom",
				bio: `<p>Tom has dedicated his career to helping early-stage startups grow by leaps and bounds through analytical frameworks. Tom was formerly the Director of Marketing at Loeb Enterprises/Scriptrelief and began his career at RR Donnelley in their tech venture group. He holds a B.S. in Mathematics and Economics from the University of Southern California. Why Maven? Tom believes that healthcare represents both the biggest opportunity and the biggest challenge for change through technology and has the power to improve women’s lives.</p>`
			},
			{
				name: "Katie Jaxheimer Agarwal",
				title: "VP of Operations & Finance",
				imgclass: "katie",
				bio: `<p>Prior to Maven, Katie was a Program Officer for the S. D. Bechtel, Jr. Foundation, leading portfolios of investments in science education and social-emotional learning. As Principal at The Parthenon Group, Katie managed consulting engagements for private equity, corporate strategy, and government clients. She also co-developed a low-cost brace for children in developing countries (check out MiracleFeet!) and evaluated new education technology investments with NewSchools Venture Fund. Katie holds a BA degree in Economics from Dartmouth College, a Master of Education degree from the Stanford Graduate School of Education, and a MBA from the Stanford Graduate School of Business.</p>`
			}
		];

		$scope.advisors = [
			{
				name: "Jenny Schneider, MD",
				detail: "Dr. Jenny Schneider is the Chief Medical Officer at Livongo Health. Prior to joining Livongo, she worked at Castlight Health and held leadership roles in the provider setting as the Chief Resident at Stanford University."
			},
			{
				name: "Jordan Shlain, MD",
				detail: "Dr. Jordan Shlain is the chairman and founder of HealthLoop. In addition to being a full time doctor, he was also appointed commissioner by the Mayor to the SF Health Service Systems Board from 2010 to 2015."
			},
			{
				name: "Rebecca Callahan, WHNP",
				detail: "Rebecca Callahan is a passionate women’s health nurse practitioner who sits on the Board of Advisors for the NYU Rory Meyers College of Nursing. She has previously worked at New York Presbyterian Hospital, The Children’s Aid Society, and both public and private OB-GYN offices."
			},
			{
				name: "Bridget Duffy, MD",
				detail: "Dr. Bridget Duffy is the Chief Medical Officer at Vocera Communications and was the first Chief Experience Officer at the Cleveland Clinic–the first senior position of its kind."
			},
			{
				name: "Nassim Assefi, MD",
				detail: "Dr. Nassim Assefi is an internist specializing in global women's health, caring for vulnerable urban patients in the US and tackling maternal mortality in low-income and post-conflict countries."
			},
			{
				name: "Brian Levine, MD",
				detail: "Dr. Brian Levine is the founding partner and practice director of Colorado Center for Reproductive Medicine in New York. In addition to his clinical practice and ongoing research, Dr. Levine is the technology editor of Contemporary OB-GYN magazine."
			},
			{
				name: "Jane van Dis, MD",
				detail: "Dr. Jane van Dis is the Medical Director for Business Development at the Ob Hospitalist Group. She previously served as an Assistant Professor at the University of Minnesota Department of OB-GYN, Director of the Medical Student OB-GYN Clerkship, and as an Associate physician with Kaiser Permanente."
			},
			{
				name: "Henry Davis",
				detail: "Henry Davis is the President and COO of cult beauty brand Glossier. Prior to launching Glossier, he was an investor at Index Ventures in London."
			},
			{
				name: "Michele Shepard",
				detail: "Michele has served as CRO and SVP of Sales and Marketing at Vertafore and Gartner."
			},
			{
				name: "Leslie Ziegler",
				detail: "Leslie Ziegler was on the founding team at startup incubator Rock Health and served as the firm’s creative director. She is now a co-founder of Bitty and an advisor with Neurotrack."
			}
		];

		$scope.openBio = (person) => {
			ModalService.openBio(person)
		}

	}]);