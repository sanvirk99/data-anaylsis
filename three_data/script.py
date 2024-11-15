# %%
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import cumestatsteamgames, cumestatsteam, gamerotation
import pandas as pd
import numpy as np
import json
import difflib
import time
import requests


def retry(func, retries=3):
    def retry_wrapper(*args, **kwargs):
        attempts = 0
        while attempts < retries:
            try:
                return func(*args, **kwargs)
            except requests.exceptions.RequestException as e:
                print(e)
                time.sleep(30)
                attempts += 1

    return retry_wrapper


def getSeasonScheduleFrame(seasons,seasonType): 

    # Get date from string
    def getGameDate(matchup):
        return matchup.partition(' at')[0][:10]

    # Get Home team from string
    def getHomeTeam(matchup):
        return matchup.partition(' at')[2]

    # Get Away team from string
    def getAwayTeam(matchup):
        return matchup.partition(' at')[0][10:]

    # Match nickname from schedule to team table to find ID
    def getTeamIDFromNickname(nickname):
        return teamLookup.loc[teamLookup['nickname'] == difflib.get_close_matches(nickname,teamLookup['nickname'],1)[0]].values[0][0] 
    
    @retry
    def getRegularSeasonSchedule(season,teamID,seasonType):
        season = str(season) + "-" + str(season+1)[-2:] # Convert year to season format ie. 2020 -> 2020-21
        teamGames = cumestatsteamgames.CumeStatsTeamGames(league_id = '00',season = season ,
                                                                      season_type_all_star=seasonType,
                                                                      team_id = teamID).get_normalized_json()
        
        teamGames = pd.DataFrame(json.loads(teamGames)['CumeStatsTeamGames'])
        teamGames['SEASON'] = season
        return teamGames    
    
    # Get team lookup table
    teamLookup = pd.DataFrame(teams.get_teams())
    
    # Get teams schedule for each team for each season
    scheduleFrame = pd.DataFrame()
  
    for season in seasons:
        for id in teamLookup['id']:
            time.sleep(1)
            tmp=pd.DataFrame(getRegularSeasonSchedule(season,id,seasonType))
            if tmp.empty:
                continue
            else:
                scheduleFrame = pd.concat([scheduleFrame,tmp])
            #scheduleFrame = scheduleFrame.append(getRegularSeasonSchedule(season,id,seasonType))
            
    scheduleFrame['GAME_DATE'] = pd.to_datetime(scheduleFrame['MATCHUP'].map(getGameDate))
    scheduleFrame['HOME_TEAM_NICKNAME'] = scheduleFrame['MATCHUP'].map(getHomeTeam)
    scheduleFrame['HOME_TEAM_ID'] = scheduleFrame['HOME_TEAM_NICKNAME'].map(getTeamIDFromNickname)
    scheduleFrame['AWAY_TEAM_NICKNAME'] = scheduleFrame['MATCHUP'].map(getAwayTeam)
    scheduleFrame['AWAY_TEAM_ID'] = scheduleFrame['AWAY_TEAM_NICKNAME'].map(getTeamIDFromNickname)
    scheduleFrame = scheduleFrame.drop_duplicates() # There's a row for both teams, only need 1
    scheduleFrame = scheduleFrame.reset_index(drop=True)
            
    return scheduleFrame



single_game_count = 0

def getSingleGameMetrics(gameID,homeTeamID,awayTeamID,awayTeamNickname,seasonYear,gameDate):
    single_game_count += 1
    print(single_game_count)
    @retry
    def getGameStats(teamID,gameID,seasonYear):
        gameStats = cumestatsteam.CumeStatsTeam(game_ids=gameID,league_id ="00",
                                               season=seasonYear,season_type_all_star="Regular Season",
                                               team_id = teamID).get_normalized_json()

        gameStats = pd.DataFrame(json.loads(gameStats)['TotalTeamStats'])
        return gameStats

    data = getGameStats(homeTeamID,gameID,seasonYear)
    data.at[1,'NICKNAME'] = awayTeamNickname
    data.at[1,'TEAM_ID'] = awayTeamID
    data.at[1,'OFFENSIVE_EFFICIENCY'] = (data.at[1,'FG'] + data.at[1,'AST'])/(data.at[1,'FGA'] - data.at[1,'OFF_REB'] + data.at[1,'AST'] + data.at[1,'TOTAL_TURNOVERS'])
    data.at[1,'SCORING_MARGIN'] = data.at[1,'PTS'] - data.at[0,'PTS']

    data.at[0,'OFFENSIVE_EFFICIENCY'] = (data.at[0,'FG'] + data.at[0,'AST'])/(data.at[0,'FGA'] - data.at[0,'OFF_REB'] + data.at[0,'AST'] + data.at[0,'TOTAL_TURNOVERS'])
    data.at[0,'SCORING_MARGIN'] = data.at[0,'PTS'] - data.at[1,'PTS']

    data['SEASON'] = seasonYear
    data['GAME_DATE'] = gameDate
    data['GAME_ID'] = gameID
    return data





def main():

    seasons = [2022]
    seasonType = 'Regular Season'

    start = time.perf_counter_ns() # Track cell's runtime
    scheduleFrame = getSeasonScheduleFrame(seasons,seasonType)
    end = time.perf_counter_ns()


    secs = (end-start)/1e9
    mins = secs/60
    print(mins)

    #wrtie frame to csv
    scheduleFrame.info()
    #scheduleFrame.to_csv('scheduleFrame.csv',index=False)
        
    print(len(scheduleFrame))
    frames = scheduleFrame.apply(lambda row: getSingleGameMetrics(row['GAME_ID'], row['HOME_TEAM_ID'], row['AWAY_TEAM_ID'], row['AWAY_TEAM_NICKNAME'], row['SEASON'], row['GAME_DATE']), axis=1)


    index_seed=frames[0].loc[0].index

    winners=pd.DataFrame(columns=index_seed) 
    losers=pd.DataFrame(columns=index_seed)




    for frame in frames:

        winner,loser = (frame.loc[0],frame.loc[1]) if frame.at[0,'W'] > frame.at[1,'W'] else (frame.loc[1],frame.loc[0])

        list1=winner.values.tolist()
        list2=loser.values.tolist()

        winners.loc[len(winners)]=list1
        losers.loc[len(losers)]=list2





    print(len(winners))
    print(len(losers))

    # winners.to_csv('winners.csv',index=False) 
    # losers.to_csv('losers.csv',index=False)


if __name__ == "__main__":
    main()
