"""Static copy: background texts, general FAQ and glossary. Kept separate from build.py."""

BACKGROUND = {
    "christmas": "Christmas Day marks the Christian celebration of the birth of Jesus and falls on 25 December in most Western churches. Many Orthodox churches that follow the Julian calendar celebrate it on 7 January instead. It is a public holiday in most countries with a Christian heritage, and in many of them shops, offices and public transport close or run reduced timetables.",
    "christmas-eve": "Christmas Eve is the day before Christmas Day, 24 December. In several countries, including Germany, Poland and Estonia, the main family meal and the exchange of gifts take place on the evening of the 24th. It is a public holiday in some countries, and a shortened working day in some workplaces elsewhere.",
    "new-years-eve": "New Year's Eve is the last day of the Gregorian calendar year, 31 December. The new year arrives first on islands such as Kiritimati (UTC+14) and last in time zones such as UTC−12, so the celebrations with fireworks and midnight countdowns roll around the world over about 26 hours.",
    "new-years-day": "New Year's Day, 1 January, is the first day of the Gregorian calendar and one of the few public holidays observed in almost every country. Some countries and communities also celebrate other new years on different dates, for example Lunar New Year, Nowruz or Rosh Hashanah.",
    "valentines-day": "Valentine's Day on 14 February is a day for cards, flowers and romantic gestures. It takes its name from the Christian feast of Saint Valentine, and its romantic meaning grew through medieval literature. It is not a public holiday in most countries.",
    "st-patricks-day": "St. Patrick's Day on 17 March honours Saint Patrick, the patron saint of Ireland. It is a public holiday in Ireland and Northern Ireland, and is celebrated with parades and green decorations in many places with large Irish communities, such as the United States.",
    "easter": "Easter Sunday celebrates the resurrection of Jesus in the Christian tradition. Western churches calculate it as the first Sunday after the first full moon on or after 21 March, so it can fall between 22 March and 25 April. Orthodox churches use the Julian calendar for the calculation, which means their Easter often falls on a different date.",
    "good-friday": "Good Friday commemorates the crucifixion of Jesus and falls two days before Easter Sunday. Because Easter moves from year to year, Good Friday moves with it. It is a public holiday in many countries across Europe, the Americas and Oceania.",
    "easter-monday": "Easter Monday is the day after Easter Sunday. Like the rest of the Easter holidays it moves each year, and it is a public holiday in many European countries and several others, which often makes Easter a four-day weekend.",
    "april-fools-day": "April Fools' Day on 1 April is a day of practical jokes and hoaxes in many countries. Newspapers, brands and websites often publish made-up stories. It is not a public holiday anywhere that we list.",
    "earth-day": "Earth Day on 22 April has been held since 1970 to raise support for environmental protection. It is now coordinated worldwide, and the United Nations also recognises 22 April as International Mother Earth Day. It is an awareness day, not a public holiday.",
    "mothers-day-us": "In the United States, Canada, Australia and many other countries, Mother's Day falls on the second Sunday of May. The date varies elsewhere: the United Kingdom celebrates Mothering Sunday in March, on the fourth Sunday of Lent, and some countries use a fixed calendar date.",
    "fathers-day-us": "In the United States, the United Kingdom, Canada and many other countries, Father's Day falls on the third Sunday of June. Other countries choose different dates. Germany, for example, observes Father's Day on Ascension Day, and Estonia celebrates it on the second Sunday of November.",
    "memorial-day": "Memorial Day, the last Monday of May, honours members of the United States armed forces who died while serving. It is a federal holiday, and for many Americans it marks the unofficial start of summer.",
    "independence-day-us": "Independence Day, often called the Fourth of July, commemorates the adoption of the Declaration of Independence on 4 July 1776. It is a federal holiday in the United States, usually celebrated with fireworks, parades and barbecues.",
    "labor-day-us": "Labor Day in the United States and Canada falls on the first Monday of September and honours workers. Most other countries mark International Workers' Day on 1 May instead.",
    "halloween": "Halloween on 31 October is the evening before All Saints' Day. It is often linked to older harvest and autumn festivals in the Celtic regions. Costumes, carved pumpkins and trick-or-treating became popular worldwide through the United States. It is not a public holiday in most countries.",
    "thanksgiving-us": "Thanksgiving in the United States falls on the fourth Thursday of November and is a federal holiday, traditionally marked with a family meal. Canada celebrates its own Thanksgiving on the second Monday of October.",
    "black-friday": "Black Friday is the day after US Thanksgiving and the traditional start of the Christmas shopping season, with discounts in shops and online. The idea has spread well beyond the United States, but it is not a public holiday.",
    "cyber-monday": "Cyber Monday is the Monday after US Thanksgiving and is aimed at online shopping deals. The term was introduced in 2005 by the US National Retail Federation. It is a shopping event, not a public holiday.",
    "summer-solstice": "The June solstice happens around 20 or 21 June. It is the longest day of the year in the northern hemisphere and the shortest in the southern hemisphere. The exact moment changes from year to year, so this page counts down to 21 June as a close approximation.",
    "winter-solstice": "The December solstice happens around 21 or 22 December. It is the shortest day in the northern hemisphere and the longest in the southern hemisphere. The exact moment changes from year to year, so this page counts down to 21 December as a close approximation.",
}

# named-event slug -> English holiday name slug used in country data (for "countries that observe it")
NAMED_TO_HOLIDAY = {
    "christmas": "christmas-day",
    "christmas-eve": "christmas-eve",
    "new-years-day": "new-years-day",
    "easter": "easter-sunday",
    "good-friday": "good-friday",
    "easter-monday": "easter-monday",
}

GENERAL_FAQ = [
    ("What is a public holiday?",
     "A public holiday is a day set by law or government decision on which most workplaces and schools close and many people have the day off. Some holidays are religious, some national or historical, and some mark workers or the seasons. Which days count, and how they are paid, depends on each country's rules."),
    ("What is the difference between a public holiday and a bank holiday?",
     "In some countries, such as the United Kingdom and Ireland, the term bank holiday is used for public holidays, because banks and many businesses close. In other countries a bank holiday can mean a day when only banks and financial markets are closed. We list the days that the data source marks as public holidays and show other observances separately."),
    ("Why do some holidays apply only to some regions?",
     "Many countries let states, provinces or regions set their own holidays. Germany, Switzerland, the United States and Spain all have holidays that apply in some regions only. On this site, a holiday is marked Nationwide when it applies everywhere in the country, and Some regions when it applies only to part of it."),
    ("What happens when a public holiday falls on a weekend?",
     "It depends on the country. Some countries move the day off to the nearest Monday or Friday, some give a replacement day later, and some simply let the holiday pass. The dates on this site are the calendar dates of the holiday itself. For replacement rules, check the official source for the country."),
    ("Why does the date of Easter change every year?",
     "Western Easter is the first Sunday after the first full moon on or after 21 March, so it can fall between 22 March and 25 April. Good Friday, Easter Monday and several other holidays are counted from Easter, so they move with it. Orthodox churches use a different calendar for the calculation, so their Easter often falls on another date."),
    ("How does this site know whether today is a holiday?",
     "Each page contains the list of public holidays for the country and works out today's date in the country's main time zone, using your browser. That is why the answer stays correct even if you keep a page open past midnight. For countries that span several time zones, we use the time zone of the most populated or main region."),
    ("Where does the holiday data come from?",
     "The holiday lists come from the open Nager.Date project, which collects public holidays by country. We rebuild the whole site every day so that changes in the source reach the pages quickly."),
    ("Can the dates be wrong?",
     "Governments sometimes add, move or cancel holidays at short notice, and some holidays depend on religious or astronomical decisions. We do our best to keep the data current, but you should confirm important dates with an official government source before you book travel or plan business around them."),
    ("Does the site include every country?",
     "We list the countries and territories for which the data source has public holiday information. If a country is missing, it is because no list is available in the source, not because it has no holidays."),
    ("How is the number of days until a holiday calculated?",
     "We count the calendar days from today's date to the date of the holiday, using your device's date. Today counts as zero, so a holiday tomorrow is one day away. The week count shown next to it simply divides that number by seven."),
]

GLOSSARY = [
    ("Public holiday", "A day recognised by law or government on which most workplaces and schools are closed."),
    ("Nationwide holiday", "A public holiday that applies in the whole country."),
    ("Regional holiday", "A holiday that applies only in some states, provinces or regions of a country."),
    ("Observance", "A day that is marked or remembered but is not a day off for most people, for example Valentine's Day or Mother's Day in many countries."),
    ("Movable holiday", "A holiday whose date changes every year, such as Easter and the holidays counted from it."),
    ("Day in lieu", "A replacement day off given when a public holiday falls on a weekend. Whether one is given depends on local law."),
    ("Bridge day", "A working day between a public holiday and a weekend that many people take off to get a longer break."),
]

REGION_TEXT = {
    "Europe": "Most European countries combine religious holidays, such as Christmas, Easter and Pentecost, with national days and Labour Day on 1 May. Many follow the Western Easter calendar, while several Orthodox countries celebrate Easter on a different date.",
    "Americas": "Public holidays in the Americas mix national independence days, religious holidays and days that honour workers. Federal countries such as the United States, Canada and Brazil also have holidays that apply only in some states or provinces.",
    "Asia": "Holiday calendars in Asia combine national days with religious and lunar-calendar festivals. Many dates, such as Lunar New Year, Eid and Diwali, depend on the lunar or lunisolar calendar and move from year to year relative to the Gregorian calendar.",
    "Africa": "African holiday calendars mix independence and liberation days with Christian and Islamic holidays. Islamic holidays follow the lunar calendar, so their dates in the Gregorian calendar move by about ten to eleven days every year.",
    "Oceania": "Public holidays in Oceania include national days, Christian holidays and, in Australia and New Zealand, several days that are specific to a state or region. Seasons are the reverse of the northern hemisphere, so Christmas falls in summer.",
}
