$(document).ready(function() {
	$("#shares").keyup(function() {
		var numShares = Number($(this).val());
		var currentPrice = Number($("#current").html());
		var total = numShares * currentPrice;
		$("#total").text(total);
	});
});