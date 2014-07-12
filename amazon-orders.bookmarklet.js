//TODO: load jQuery

$output = $("<textarea rows='12' cols='80'></textarea>");
$output.val([
    "date",
    "order no",
    "delivery address",
    "price",
    "items",
].join(","));

var $orders = $("div.order-level");

$orders.each(function(i, elem) {

    var data = [];

    function addColumn(s)
    {
        s = s.replace(/,/g, "");
        s = s.replace(/\n/g, ";");
        data.push(s);
    }

    // date
    addColumn(new Date($(elem).find("h2").text()).toDateString());

    $details = $(elem).find(".order-details");

    // order #
    addColumn($details.find(".info-title:contains('Order #')").parent().children(".info-data").text());

    // delivery address
    $addr = $details.find(".info-title:contains('Delivery Address')");

    if ($addr.length > 0)
    {
        addColumn($addr.parent().children(".info-data").html().replace(/<br>/g, "\n").replace(/^\s+/, "").replace(/\s+$/, ""));
    }
    else
    {
        addColumn("");
    }

    // price
    addColumn($details.find(".price").text().replace("$", ""));

    // items
    {
        var items = [];
    
        $(elem).parent().find(".item-title").each(function(j, elem2) {
            var s = $(elem2).text();
            s = s.replace(/^\s+/, "");
            s = s.replace(/\s+$/, "");
            items.push(s);
        });
    
        addColumn(items.join(";"));
    }

    $output.val($output.val() + "\n" + data.join(","));

    console.log(data.join(","));
});

$("body").append($output);
