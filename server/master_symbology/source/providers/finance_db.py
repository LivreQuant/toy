import financedatabase as fd

equities = fd.Equities()

equities.show_options(market=['New York Stock Exchange', 'NASDAQ Global Select'])

stocks = equities.select(market=['New York Stock Exchange', 'NASDAQ Global Select'])
