# 可以自己import我们平台支持的第三方python模块，比如pandas、numpy等。
import numpy as np
import pandas as pd
# 在这个方法中编写任何的初始化逻辑。context对象将会在你的算法策略的任何方法之间做传递。
def init(context):
    # context内引入全局变量s1
    context.s1 = "AG"
    context.lst_contracts = ["AG","AU","JM","J","RB","I","CU","ZN"]
    # 初始化时订阅合约行情。订阅之后的合约行情会在handle_bar中进行更新。
    context.command = "N"
    subscribe(context.s1+"88")
    # 实时打印日志
    logger.info("RunInfo: {}".format(context.run_info))
    
    context.selected_contract =""

# before_trading此函数会在每天策略交易开始前被调用，当天只会被调用一次
def before_trading(context):
    pass

def contracts_command(context,bar_dict):
    rt = list(map(lambda x :calc_roll_yields(context,bar_dict,x),context.lst_contracts))
    rt = pd.Series(rt,index=context.lst_contracts)
    return rt

    
def get_trading_contracts(context,bar_dict):
    _rt = contracts_command(context,bar_dict)
    low_rt = _rt[_rt<0]
    high_rt = _rt[_rt>0]
    print(_rt)
    if len(high_rt)>0:
        long_contract = high_rt.argmax()
        long_contract = long_contract+"88"
        # long_contract = get_dominant_future(long_contract)
    else:
        long_contract = ""
    
    
    holding_contracts = context.portfolio.positions.keys()
    if len(holding_contracts)>0:
        prefix = list(map(lambda x: instruments(x).underlying_symbol,holding_contracts))
        mapping = dict(zip(prefix,holding_contracts))
        
        holding_rt = _rt.loc[prefix]
        to_clear = holding_rt[holding_rt<0].index.tolist()
        to_clear = pd.Series(to_clear).replace(mapping).values.tolist()
    else:
        to_clear = []
    if len(to_clear)>0:
        context.command = ["S",to_clear]
    else:
        if len(long_contract)>0:
            context.command = [ "B",long_contract]
        else:
            context.command =  "N"
        
def commands_execuate(context,bar_dict):
    results = context.command
    if len(results) == 2:
        if results[0] == "S":
            to_sell = results[1]
            feedBacks = close_Contracts(context,bar_dict, to_sell)
            if feedBacks == "D":
                context.command = "N"
            else:
                pass
        elif results[0] == "B":
            to_buy = results[1]
            subscribe(to_buy)
            open_to_target(context,bar_dict,to_buy,2)
            
        
def open_to_target(context,bar_dict,s,amount):
    _bqt,_sqt = get_positions(context,s)
    left = amount - _bqt
    if left>0:
        buy_open(s,left)
    else:
        context.command = "N"
        if left<0:
            logger.warn("whats wrong?")
    

# 你选择的期货数据更新将会触发此段逻辑，例如日线或分钟线更新
def handle_bar(context, bar_dict):
    
    if context.command == "N":
        get_trading_contracts(context,bar_dict)
    else:
        commands_execuate(context,bar_dict)


# after_trading函数会在每天交易结束后被调用，当天只会被调用一次
def after_trading(context):
    pass
        
def close_Contracts(context,bar_dict, contracts):
    feedBacks = list(set(map(lambda x: close_oneContract(context,bar_dict,x),contracts)))
    if len(feedBacks) == 1 and feedBacks[0] == "D":
        return "D"

def get_positions(context,s):
    return context.portfolio.positions[s].buy_quantity,context.portfolio.positions[s].sell_quantity
    

def calc_roll_yields(context,bar_dict,contract_prefix):
    
    all_contracts = get_future_contracts(contract_prefix)
    if len(all_contracts) > 0:
        dominants_contract = get_dominant_future(contract_prefix)
        
        spot_contract = all_contracts[0]
        
        spot_price = bar_dict[spot_contract].last
        dominant_price = bar_dict[dominants_contract].last
        
        spot_DTM = instruments(spot_contract).days_to_expire()
        dominants_DTM = instruments(dominants_contract).days_to_expire()
        if not dominants_DTM == spot_DTM:
            roll_yields = np.log(spot_price/dominant_price)*(365/(dominants_DTM-spot_DTM))
        else:
            roll_yields = -999
    else:
        roll_yields = -999
    return roll_yields
    
def stoploss_backup(context,bar_dict):
    holding_contracts = sorted(list(context.portfolio.positions.keys()))

    buy_avg_holding_prices = list(map(lambda x: context.portfolio.positions[x].buy_avg_holding_price,holding_contracts))
    sell_avg_holding_prices = list(map(lambda x: context.portfolio.positions[x].sell_avg_holding_price,holding_contracts))

    # cur_prices = list(map(lambda x: bar_dict[x].last,holding_contracts))

    feedBacks = {}

    for i, contract in enumerate(holding_contracts):

        _bqt,_sqt = get_positions(context,contract)

        if _bqt>0 and buy_avg_holding_prices[i] > bar_dict[contract].last*1.05:
            print("zhisun11")
            feedBacks[contract] = close_oneContract(context,bar_dict,contract)
        if _sqt>0 and sell_avg_holding_prices[i] < bar_dict[contract].last*0.95:
            print("zhisun2")
            feedBacks[contract] = close_oneContract(context,bar_dict,contract)
    fds = list(set(feedBacks.values()))
    if (len(fds) == 1 and fds[0] == "D") or len(feedBacks) == 0:
        return "D"

    else:
        feedBacks_c = feedBacks.copy()
        for fk in feedBacks_c:
            if feedBacks.get(fk) == "D":
                feedBacks.pop(fk)
        return feedBacks
    

def close_oneContract(context, bar_dict, s):
    _bqt, _sqt = get_positions(context, s)
    if _bqt > 0:
        # _bqt = min(int(bar_dict[s].volume*0.25),_bqt)
        sell_close(s, _bqt)
    elif _sqt > 0:
        # _sqt = min(int(bar_dict[s].volume*0.25),_sqt)
        buy_close(s, _sqt)

    _bqt, _sqt = get_positions(context, s)
    if _bqt == _sqt == 0:
        return "D"
