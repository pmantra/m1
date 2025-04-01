angular.module('mavenApp')
	.factory('MvnUiUtils', [function() {
		
		const _hexToRgb = hex => {
			// shoutout to https://stackoverflow.com/questions/5623838/rgb-to-hex-and-hex-to-rgb for this function
			// Expand shorthand form (e.g. "03F") to full form (e.g. "0033FF")
		    const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
		    const parsedHex = hex.replace(shorthandRegex, function(m, r, g, b) {
		        return r + r + g + g + b + b;
		    })

		    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(parsedHex)
		    
			const rgb = {
		        r: parseInt(result[1], 16),
		        g: parseInt(result[2], 16),
		        b: parseInt(result[3], 16)
		    }
		
			return rgb ? `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})` : null
		}
		
		const _getRgb = color => {
			if (color.indexOf('#') !== -1) return _hexToRgb(color)
			return color
		}
		
		const _getColorStep = (color1, color2, factor) => {
		    let result = color1.slice();
		    for (let i = 0; i < 3; i++) {
		        result[i] = Math.round(result[i] + factor * (color2[i] - color1[i]));
		    }
		    return result;
		}
		
		const _interpolateColors = (startColor, endColor, steps) => {
			const stepFactor = 1 / (steps - 1)
			let interpolatedColorValues = []
			
			// strip out 'rgb()' from color string
			const startValue = startColor.match(/\d+/g).map(Number)
			const endValue = endColor.match(/\d+/g).map(Number)
			
			for (let i = 0; i < steps; i++) {
				interpolatedColorValues.push(_getColorStep(startValue, endValue, stepFactor * i))
			}
			
			// put 'rgb()' back!
			const rgbArray = interpolatedColorValues.map((values) => {
				return `rgb(${values[0]}, ${values[1]}, ${values[2]})`
			})
			
			return rgbArray
		}
			
		return {
			getInterpolatedColors: (startColor, endColor, steps) => {
				const startRgb = _getRgb(startColor)
				const endRgb = _getRgb(endColor)
				return _interpolateColors(startRgb, endRgb, steps)
			}
		}
}]);

