def compute_score(rank_winner, rank_looser, sets_diff, debug = False, fixed_reward_points = 20, per_set_reward_points = 10, d = 100.0):
  if sets_diff not in [1, 2, 3]:
    raise Exception("The sets difference must 1, 2 or 3")
  if rank_winner <= 0 or rank_looser <= 0: 
    raise Exception("Rank can not be negative")
    
  # k represents the maximum number of points that a player can 
  # change depending on their relative strength. e.g. max: 25
  k = fixed_reward_points + sets_diff * per_set_reward_points
  rank_diff = rank_winner - rank_looser
    
  # win expectation : tune d parameter for making it more smoothly. 
  # with default d, the behaviour is as follows. if A and B both have 500
  # and A wins B with 3 sets of difference, next win expectancy will 
  # be changed from 0.5 to around 0.75 
  winner_win_expectancy = 1 / ( 10 ** ( - rank_diff / d ) + 1 )
  looser_win_expectancy = 1 - winner_win_expectancy 
    
  # new rank. weight based on win expectancy probability. 
  new_rank_winner = rank_winner + (1 - winner_win_expectancy) * k
  new_rank_looser = rank_looser + (0 - looser_win_expectancy) * k
  if debug: print '**     Updating     **'
  if debug: print 'rank difference is    ', rank_diff 
  if debug: print 'sets difference       ', sets_diff
  if debug: print 'winner win expectancy ', winner_win_expectancy   
  if debug: print 'looser win expectancy ', looser_win_expectancy
  if debug: print 'winner wins           ', new_rank_winner - rank_winner
  if debug: print 'looser loses          ', new_rank_looser - rank_looser
  return [new_rank_winner, new_rank_looser]
