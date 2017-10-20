import sys, os
sys.path.append(os.getcwd() + "/libtcodpy")

import libtcodpy as libtcod
import math
import textwrap
import shelve

##############################
# INITIALIZATION
##############################

# Size of the window
SCREEN_WIDTH = 90
SCREEN_HEIGHT = 60

# Size of the Map
MAP_WIDTH = 80
MAP_HEIGHT = 45

#Size and coord's for GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
LEVEL_SCREEN_WIDTH = 40

color_light_wall = libtcod.Color(130, 110, 50)
color_dark_wall = libtcod.darker_grey
color_light_ground = libtcod.Color(200, 180, 50)
color_dark_ground = libtcod.dark_grey

LIMIT_FPS = 20

# Parameters for the dungeon generator
BOSS_ROOM_MAX_WIDTH = 50
BOSS_ROOM_MAX_HEIGHT = 30
BOSS_ROOM_MIN_WIDTH = 30
BOSS_ROOM_MIN_HEIGHT = 10
NUMBER_OF_PILLARS = 15

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 5

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

# XP and level-up
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

# Spell values
CONFUSE_NUM_TURNS = 5
CONFUSE_RANGE = 8

LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 30

LIFESTEAL_RANGE = 8  
LIFESTEAL_DAMAGE = 25

################################
# CLASSES
################################


class Object:

  # This is a generic object: player, monster, item, etc..
  def __init__(self, x, y, char, name, color, blocks = False, always_visible = False, fighter=None, ai=None, item=None, equipment=None):
    self.always_visible = always_visible
    self.name = name
    self.blocks = blocks
    self.x = x
    self.y = y
    self.char = char
    self.color = color
    
    self.item = item
    if self.item:
      self.item.owner = self

    self.equipment = equipment
    if self.equipment:
      self.equipment.owner = self

      self.item = Item()
      self.item.owner = self


    self.fighter = fighter
    if self.fighter: # let the fighter component know who owns it
      self.fighter.owner = self

    self.ai = ai
    if self.ai: # let the AI comonent know who owns it
      self.ai.owner = self

  def move(self, dx, dy):
    if not is_blocked(self.x + dx, self.y + dy):
      self.x += dx
      self.y += dy

  def move_towards(self, target_x, target_y):
    # vector from the object to the target
    delta_x = target_x - self.x
    delta_y = target_y - self.y

    distance = math.sqrt(delta_x ** 2 + delta_y ** 2)

    dx = int(round(delta_x/distance))
    dy = int(round(delta_y/distance))


    if map[self.x + dx][self.y].blocked:
      if delta_y < 0:
        self.move(0, -1)
      elif delta_y > 0:
        self.move(0, 1)

    elif map[self.x][self.y + dy].blocked:
      if delta_x < 0:
        self.move(-1, 0)
      elif delta_x > 0:
        self.move(1, 0)

    else:
      self.move(dx, dy)


  def distance_to(self, other):
    # return distance to another object
    dx = other.x - self.x
    dy = other.y - self.y
    return math.sqrt(dx ** 2 + dy ** 2)

  def send_to_back(self):
    # make this object drawn first, so that it will appear below all others
    global objects
    objects.remove(self)
    objects.insert(0, self)

  def draw(self):
    # Draw only if object is in the fov
    if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or 
         (self.always_visible and map[self.x][self.y].explored)):
      libtcod.console_set_default_foreground(con, self.color)
      libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

  def clear(self):
    libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

class Fighter:
  # Combat related properties and methods
  def __init__(self, hp, defense, power, xp, death_function = None):
    self.base_max_hp = hp
    self.hp = hp
    self.base_defense = defense
    self.base_power = power
    self.xp = xp
    self.death_function = death_function
 
  @property
  def power(self):
    bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
    return self.base_power + bonus

  @property
  def defense(self):
    bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
    return self.base_defense + bonus

  @property
  def max_hp(self):
    bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
    return self.base_max_hp + bonus

  @property
  def life_steal(self):
    bonus = sum(equipment.life_steal_bonus for equipment in get_all_equipped(self.owner))
    return bonus


  def attack(self, target):
    # a simple formual for attack damage
    damage = self.power - target.fighter.defense

    if damage > 0:
      # make the target take some damage
      message(self.owner.name.capitalize() + " attacks " + target.name + " for " + str(damage) + " hit points.", libtcod.lightest_azure)
      target.fighter.take_damage(damage)
      if target != player:
        player.fighter.heal(player.fighter.life_steal)

    else:
      message(self.owner.name.capitalize() + " attacks " + target.name + " but is has no effect!", libtcod.desaturated_azure)

  def take_damage(self, damage):
    # apply damage if possible
    if damage > 0:
      self.hp -= damage

      if self.hp <= 0:
        function = self.death_function
        if function is not None:
          function(self.owner)
        if self.owner != player:
          player.fighter.xp += self.xp

  def heal(self, amount):
    self.hp += amount
    if self.hp >= self.max_hp:
      self.hp = self.max_hp

class Projectile:
  #AI for projectile

  def __init__(self, target_x, target_y):
    self.target_x = target_x
    self.target_y = target_y

  def take_turn(self):
    projectile = self.owner
    projectile.move_towards(target_x, target_y)

    if self.x == player.x and self.y == player.y:
      player.take_damage(15)
      projectile.take_damage(1)

    elif map[self.x][self.y].blocked:
      projectile.take_damage(1)
    
class BasicMonster:
  #AI for a basic monster
  def take_turn(self):
    # monster takes its turn. If you can see it, it can see you
    monster = self.owner
    if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

      # move towards player if far away
      if monster.distance_to(player) >= 2:
        monster.move_towards(player.x, player.y)
      
      # now the monster is close enough to attack!
      elif player.fighter.hp > 0:
        monster.fighter.attack(player)

class BossMonster:
  # AI for bosses
  def take_turn(self):
  
    boss = self.owner
    if libtcod.map_is_in_fov(fov_map, boss.x, boss.y):
      if boss.distance_to(player) >= 5:
        message('The ' + boss.name.capitalize() + ' begins casting Fireball!', libtcod.red)
        cast_fireball(boss.x, boss.y, player.x, player.y)

      elif boss.distance_to(player) >= 2:
        boss.move_towards(player.x, player.y)

      else:
        boss.fighter.attack(player)

class ConfusedMonster:
  # AI for a temporarily confused monster
  def __init__(self, old_ai, num_turns = CONFUSE_NUM_TURNS):
    self.old_ai = old_ai
    self.num_turns = num_turns

  def take_turn(self):
    if self.num_turns > 0:
      # Move in a random direction until no longer confused
      self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
      self.num_turns -= 1

    else:
      self.owner.ai = self.old_ai
      message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class Tile:
  # a tileof the map, and its properties
  def __init__(self, blocked, block_sight = None):
    self.blocked = blocked

    self.explored = False

    # by default, if a tile is blocked, it also blocks sight
    if block_sight is None: block_sight = blocked
    self.block_sight = block_sight

class Equipment:
  # an object can be equipped granting bonuses and such
  def __init__(self, slot, is_ranged = False, power_bonus = 0, defense_bonus = 0, max_hp_bonus = 0, life_steal_bonus = 0):
    self.power_bonus = power_bonus
    self.defense_bonus = defense_bonus
    self.max_hp_bonus = max_hp_bonus
    self.life_steal_bonus = life_steal_bonus

    self.slot = slot
    self.is_equipped = False
    self.is_ranged = is_ranged

  def toggle_equip(self):
    if self.is_equipped:
      self.dequip()
    else:
      self.equip()

  def equip(self):
    old_equipment = get_equipped_in_slot(self.slot)
    if old_equipment is not None:
      old_equipment.dequip()

    self.is_equipped = True
    message('You have equipped ' + self.owner.name + '!', libtcod.light_green)
    self.owner.name += ' *'

  def dequip(self):
    if not self.is_equipped: return

    self.is_equipped = False
    self.owner.name = self.owner.name[0:-2]
    message('You are no longer using ' + self.owner.name + '!', libtcod.light_yellow)
    
def get_equipped_in_slot(slot):
  for obj in inventory:
    if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
      return obj.equipment
  return None

def get_all_equipped(obj):
  if obj == player:
    equipped_list = []
    for item in inventory:
      if item.equipment and item.equipment.is_equipped:
        equipped_list.append(item.equipment)
    return equipped_list

  else:
    return []

class Rect:
  # a rectangle on the map, used to define rooms or halls
  def __init__(self, x, y, w, h):
    self.x1 = x
    self.y1 = y
    self.x2 = x + w
    self.y2 = y + h

  def center(self):
    center_x = (self.x1 + self.x2)/2
    center_y = (self.y1 + self.y2)/2
    return (center_x, center_y)

  def intersect(self, other):
    return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Item:
  
  def __init__(self, collectable = True, use_function = None):
    self.use_function = use_function
    self.collectable = collectable

  def pick_up(self):
  
    if len(inventory) >= 26:
      message('Your inventory is full. Can not pick up ' + self.owner.name + '.', libtcod.yellow)
    else:
      if self.collectable:
        inventory.append(self.owner)
        objects.remove(self.owner)
        message('You picked up a ' + self.owner.name + '!', libtcod.green)

        equipment = self.owner.equipment
        if equipment and get_equipped_in_slot(equipment.slot) is None:
          equipment.equip()
      else:
        message('That object is not collectable.', libtcod.red)

  def drop(self):
    objects.append(self.owner)
    inventory.remove(self.owner)
    self.owner.x = player.x
    self.owner.y = player.y
    message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

  def use(self):
    if self.owner.equipment:
      self.owner.equipment.toggle_equip()
      return

    if self.use_function is None:
      message('The ' + self.owner.name + ' cannot be used.')
    else:
      if self.use_function() != 'cancelled':
        inventory.remove(self.owner)

#############################
# FUNCTIONS
#############################

def is_blocked(x, y):
  # first, test map tile
  if map[x][y].blocked:
    return True

  # now check for any blocking objects
  for object in objects:
    if object.blocks and object.x == x and object.y == y:
      return True

  return False

def create_room(room):
  global map
  # go through the tiles in the rectangle and make them passable
  for x in range(room.x1 + 1, room.x2):
    for y in range(room.y1 + 1, room.y2):
      map[x][y].blocked = False
      map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
  global map
  # create horizantal hallway
  for x in range(min(x1, x2), max(x1, x2) + 1):
    map[x][y].blocked = False
    map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
  global map
  # create vertical hallways.
  for y in range(min(y1, y2), max(y1, y2) + 1):
    map[x][y].blocked = False
    map[x][y].block_sight = False

def random_choice_index(chances):  #choose one option from list of chances, returning its index

    #the dice will land on some number between 1 and the sum of the chances
    dice = libtcod.random_get_int(0, 1, sum(chances))
 
    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0

    for w in chances:
        running_sum += w
 
        #see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1
 
def random_choice(chances_dict):
    #choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()
 
    return strings[random_choice_index(chances)]
 
def from_dungeon_level(table):
  #returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
  for (value, level) in reversed(table):
    if dungeon_level >= level:
      return value
  return 0

def get_random_stat():
  global stat_defense, stat_power
  global stat_lifesteal, stat_hp

  stat_defense, stat_power = 0, 0
  stat_lifesteal, stat_hp = 0, 0

  stat_chances = {}
  stat_chances['health'] =       30
  stat_chances['defense'] =      40
  stat_chances['power'] =        25
  stat_chances['lifesteal'] =    5

  choice = random_choice(stat_chances)

  if choice == 'health':
    stat_hp = 25
  elif choice == 'defense':
    stat_defense = 2
  elif choice == 'power':
    stat_power = 3
  elif choice == 'lifesteal':
    stat_lifesteal = 5

  return choice, stat_power, stat_defense, stat_hp, stat_lifesteal

def place_objects(room):
  global stat_defense, stat_power
  global stat_lifesteal, stat_hp

  stat_defense, stat_power = 0, 0
  stat_lifesteal, stat_hp = 0, 0

  # max number of monsters per room 
  max_monsters = from_dungeon_level([[2, 1], [4, 4], [6, 6]])
 
  # chance of each monster type
  monster_chances = {}
  monster_chances['Alien Weakling'] = 80
  monster_chances['Alien Invader'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

  # max number of items per room
  max_items = from_dungeon_level([[1, 1], [2, 4]])

  # chance of each item
  item_chances = {}
  # scrolls and health pots
  item_chances['health'] = 35
  item_chances['lightning'] =     from_dungeon_level([[25, 2]])
  item_chances['confuse'] =       from_dungeon_level([[25, 6]])
  item_chances['lifesteal'] =     from_dungeon_level([[10, 3]])
  # basic items
  item_chances['sword'] =         from_dungeon_level([[5, 2]])
  item_chances['bow'] =           from_dungeon_level([[5, 2]])
  item_chances['armor'] =         from_dungeon_level([[7, 4]])
  item_chances['shield'] =        from_dungeon_level([[15, 6]])
  # magic items
  item_chances['magic sword'] =   from_dungeon_level([[5, 5]])  
  item_chances['magic bow'] =     from_dungeon_level([[5, 7]])
  item_chances['magic armor'] =   from_dungeon_level([[5, 6]])
  item_chances['magic shield'] =  from_dungeon_level([[5, 8]])

  # choose random number of monsters
  num_monsters = libtcod.random_get_int(0, 0, max_monsters)

  # determine coord for monsters randomly
  for i in range(num_monsters):
    x = libtcod.random_get_int(0, room.x1 + 3, room.x2 - 3)
    y = libtcod.random_get_int(0, room.y1 + 3, room.y2 - 3)
    
    # if the tile is available pick a monster type and put it there
    if not is_blocked(x, y):
  
      choice = random_choice(monster_chances)

      if choice == 'Alien Weakling':
        fighter_component = Fighter(hp = 10 + 10 * player.level, defense = 0 + 0.25 * player.level, 
                                                   power =  0.5 * player.level + 4, xp = 20 + 5 * player.level, death_function = monster_death)
        ai_component = BasicMonster()
        monster = Object(x, y, 'X', 'Alien Weakling', libtcod.desaturated_green, blocks = True, always_visible = False, fighter = fighter_component, ai = ai_component)

      elif choice == 'Alien Invader':
        fighter_component = Fighter(hp = 20 + 15 * player.level, defense = 2 + 0.25 * player.level, 
                                                   power = 0.5 * player.level + 7, xp = 50 + 10 * player.level, death_function = monster_death)
        ai_component = BasicMonster()
        monster = Object(x, y, 'X','Alien Invader', libtcod.darkest_green, blocks = True, always_visible = False, fighter = fighter_component, ai = ai_component)

        
    objects.append(monster)

    num_items = libtcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
      x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
      y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
      
      if not is_blocked(x, y):
  
        choice = random_choice(item_chances)

        if choice == 'health':
          item_component = Item(use_function = cast_heal)
          item = Object(x, y, '*', 'health potion', libtcod.fuchsia, always_visible = True, item = item_component)
        
        elif choice == 'confuse':
          item_component = Item(use_function = cast_confuse)
          item = Object(x, y, '#', 'Scroll of Confuse', libtcod.sepia, item = item_component)
   
        elif choice == 'lightning':
          item_component = Item(use_function = cast_lightning)
          item = Object(x, y, '#', 'Scroll of Lightning', libtcod.dark_violet, item = item_component) 
  
        elif choice == 'lifesteal':
          item_component = Item(use_function = cast_lifesteal)
          item = Object(x, y, '#', 'Scroll of Vampirism', libtcod.dark_crimson, item = item_component)

        elif choice == 'sword':
          equipment_component = Equipment(slot = 'right hand', power_bonus = 2)
          item = Object(x, y, 't', 'Sword', libtcod.white, equipment = equipment_component)

        elif choice == 'shield':
          equipment_component = Equipment(slot = 'left hand', defense_bonus = 1)
          item = Object(x, y, ')', 'Shield', libtcod.white, equipment = equipment_component)
          
        elif choice == 'bow':
          equipment_component = Equipment(slot = 'right hand', is_ranged = True, power_bonus = 0)
          item = Object(x, y, 'D', 'Bow', libtcod.white, equipment = equipment_component)

        elif choice == 'armor':
          equipment_component = Equipment(slot = 'body', defense_bonus = 3)
          item = Object(x, y, 'A', 'Armor', libtcod.white, equipment = equipment_component)

        elif choice == 'magic sword':
          bonus_stat = get_random_stat()

          # Swords shouldn't grant defense bonuses
          while bonus_stat[0] == 'defense':
            bonus_stat = get_random_stat()

          equipment_component = Equipment(slot = 'right hand', power_bonus = bonus_stat[1] + 3, 
                                                       defense_bonus = bonus_stat[2], max_hp_bonus = bonus_stat[3], life_steal_bonus = bonus_stat[4])
          item = Object(x, y, 't', 'Sword of ' + bonus_stat[0].capitalize(), libtcod.green, equipment = equipment_component) 
        
        elif choice == 'magic bow':
          bonus_stat = get_random_stat()

          # Bows shouldn't grant defensive bonuses either
          while bonus_stat[0] == 'defense':
            bonus_stat = get_random_stat()

          equipment_component = Equipment(slot = 'right hand', is_ranged = True, power_bonus = bonus_stat[1] + 2, 
                                                       defense_bonus = bonus_stat[2], max_hp_bonus = bonus_stat[3], life_steal_bonus = bonus_stat[4])
          item = Object(x, y, 'D', 'Bow of ' + bonus_stat[0].capitalize(), libtcod.green, equipment = equipment_component)
        
        elif choice == 'magic armor':
          bonus_stat = get_random_stat()

          # Armor should not grant lifesteal or power bonuses
          while bonus_stat[0] == 'lifesteal' or bonus_stat[0] == 'power':
            bonus_stat = get_random_stat()

          equipment_component = Equipment(slot = 'body', power_bonus = bonus_stat[1], 
                                                       defense_bonus = bonus_stat[2] + 3, max_hp_bonus = bonus_stat[3], life_steal_bonus = bonus_stat[4])
          item = Object(x, y, 'A', 'Armor of ' + bonus_stat[0].capitalize(), libtcod.green, equipment = equipment_component)
        
        elif choice == 'magic shield':
          bonus_stat = get_random_stat()
   
          # Shields should not grant lifesteal or power bonuses either
          while bonus_stat[0] == 'lifesteal' or bonus_stat[0] == 'power':
            bonus_stat = get_random_stat()

          equipment_component = Equipment(slot = 'left hand', power_bonus = bonus_stat[1], 
                                                       defense_bonus = bonus_stat[2] + 2, max_hp_bonus = bonus_stat[3], life_steal_bonus = bonus_stat[4])
          item = Object(x, y, ')', 'Shield of ' + bonus_stat[0].capitalize(), libtcod.green, equipment = equipment_component)

        objects.append(item)
        item.send_to_back()


def make_map():
  global map, objects
  global stairs

  objects = [player]

  # fill map with 'blocked' tiles
  map = [[ Tile(True)
    for y in range(MAP_HEIGHT) ]
      for x in range(MAP_WIDTH) ]

  if (dungeon_level)%5 != 0:
    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS + 5 * dungeon_level):
      # random width/ height
      w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
      h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
      # random position inside boundaries of the map
      x = libtcod.random_get_int(0,0, MAP_WIDTH - w - 1)
      y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
    
      new_room = Rect(x, y, w, h)

      # run through other rooms to see if there is an intersection.
      failed = False
      for other_room in rooms:
        if new_room.intersect(other_room):
          failed = True
          break
    
      if not failed:
        # draw the room to the map
        create_room(new_room)
           
        (new_x, new_y) = new_room.center()

        if num_rooms == 0:
          # Player will start in first room
          player.x = new_x
          player.y = new_y
          start = Object(new_x, new_y, '^', 'Start', libtcod.darker_red, blocks = False, always_visible = True)
          objects.append(start)
 
          if dungeon_level == 5:
            equipment_component = Equipment(slot = 'right hand', is_ranged = True, power_bonus = 4, defense_bonus =  5, life_steal_bonus = 6)
            item = Object(new_x + 1, new_y, 't', "Master's Bow", libtcod.Color(200, 180, 50), blocks = False, equipment = equipment_component)
            objects.append(item)
     
        else:

          place_objects(new_room)

          (prev_x, prev_y) = rooms[num_rooms-1].center()

          if libtcod.random_get_int(0,0,1) == 1:
            create_h_tunnel(prev_x, new_x, prev_y)
            create_v_tunnel(prev_y, new_y, new_x)

          else:
            create_v_tunnel(prev_y, new_y, prev_x)
            create_h_tunnel(prev_x, new_x, new_y)

        rooms.append(new_room)
        num_rooms += 1
  
    stairs = Object(new_x, new_y, 'V', 'Stairs', libtcod.white, blocks = False, always_visible = True)
    objects.append(stairs)
    stairs.send_to_back()

  else:
    
    w = libtcod.random_get_int(0, BOSS_ROOM_MIN_WIDTH, BOSS_ROOM_MAX_WIDTH)
    h = libtcod.random_get_int(0, BOSS_ROOM_MIN_HEIGHT, BOSS_ROOM_MAX_HEIGHT)
    
    room = Rect(20, 10, w, h)

    create_room(room)

    (new_x, new_y) = room.center()
    player.x = new_x
    player.y = new_y

    equipment_component = Equipment(slot = 'right hand', is_ranged = True, power_bonus = 4, defense_bonus =  5, life_steal_bonus = 6)
    item = Object(new_x + 1, new_y, 't', 'Bow of Healing', libtcod.Color(200, 180, 50), blocks = False, equipment = equipment_component)
    objects.append(item)

    x = libtcod.random_get_int(0, room.x1 + 3, room.x2 - 3)
    y = libtcod.random_get_int(0, room.y1 + 3, room.y2 - 3)
    
    # if the tile is available pick a monster type and put it there
    if not is_blocked(x, y):

      fighter_component = Fighter(hp = 80 + 15 * player.level, defense = 5, 
                                                   power = 6, xp = 100 + 10 * player.level, death_function = boss_death)

      ai_component = BossMonster()
    
      Boss = Object(x, y, 'X','Alien Champion', libtcod.black, blocks = True, always_visible = False, fighter = fighter_component, ai = ai_component)
      objects.append(Boss)
 

    for p in range(NUMBER_OF_PILLARS + 1):
      x = libtcod.random_get_int(0, room.x1 + 1, room.x2)
      y = libtcod.random_get_int(0, room.y1 + 1, room.y2)

      while x == player.x or x == Boss.x:
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2)
      while y == player.y or y == Boss.y:
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2)

      map[x][y].blocked = True
      map[x][y].block_sight = True



def player_move_or_attack(dx, dy):
  global fov_recompute
  global game_state
  global stairs

  # Coord player is moving to/attacking
  x = player.x + dx
  y = player.y + dy

  # Try to find an attackable target there
  target = None
  for object in objects:
    if object.x == x and object.y == y:
      if object.ai is not None:
        target = object
        break
  
  if target is not None:
    player.fighter.attack(target)

  else:
    player.move(dx, dy)
    fov_recompute = True


def handle_keys():
  global fov_recompute, equipped_list
  global key
  global stairs
  key = libtcod.console_check_for_keypress()

  if key.vk == libtcod.KEY_ENTER and key.lalt:
    libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
  
  elif key.vk == libtcod.KEY_ESCAPE:
    return 'exit' # exit game
  
  if game_state == 'playing':

    # Movement Keys
    if key.vk == libtcod.KEY_UP:
      player_move_or_attack(0, -1)

    elif key.vk == libtcod.KEY_DOWN:
      player_move_or_attack(0, 1)

    elif key.vk == libtcod.KEY_LEFT:
      player_move_or_attack(-1, 0)

    elif key.vk == libtcod.KEY_RIGHT:
      player_move_or_attack(1, 0)
  
    elif key.vk == libtcod.KEY_SPACE:
      
      flag = False
      for object in get_all_equipped(player):
        if object.is_equipped and object.is_ranged:
          monster = closest_monster(10)
        
          if monster is None:
            message('No monster is close enough to attack!', libtcod.red)
            flag = True
            return
        
          if line_of_sight(player, monster):
            player.fighter.attack(monster)
            flag = True
            return
      
          else:
            message(monster.name + ' is not in your line of sight!', libtcod.red)
            flag = True
            return
      
      if not flag:
        message('You do not have a ranged weapon equipped!',libtcod.red)

    else: 

      key_char = chr(key.c)

      if key_char == 'v':
        if stairs.x == player.x and stairs.y == player.y:
          next_level()

      if key_char == 'g':
        for object in objects:
          if object.x == player.x and object.y == player.y and object.item:
            object.item.pick_up()
       

      if key_char == 'i':
        chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
        if chosen_item is not None:
          chosen_item.use()

      if key_char == 'd':
        chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
        if chosen_item is not None:
          chosen_item.drop()

      if key_char == 'c':
        level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
        msgbox('Character Information\n\nLevel: ' + str(player.level) + 
                              '\nMax HP: ' + str(player.fighter.max_hp) + 
                                '\nAttack: ' + str(player.fighter.power) + 
                                  '\nDefense: ' + str(player.fighter.defense) +
                                    '\nLife Steal: ' + str(player.fighter.life_steal), CHARACTER_SCREEN_WIDTH)

      return 'didnt-take-turn'

def next_level():
  global dungeon_level

  message('You take a moment to rest and recover your strength.', libtcod.light_violet)
  player.fighter.heal(player.fighter.max_hp/2)
  
  message('After a moment of peace, you venture further into the mine..', libtcod.light_violet)
  
  dungeon_level += 1
  make_map()

  initialize_fov()

def initialize_fov():
  global fov_recompute, fov_map
  fov_recompute = True

  fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
  for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
      libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
        
  libtcod.console_clear(con)

def render_all():
  global fov_map, color_dark_wall
  global color_light_wall, color_dark_ground
  global color_light_ground
  global fov_recompute
  global level_up_xp

  level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR


  if fov_recompute:
    # recompute the fov if needed (player moved or something)
    fov_recompute = False
    libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    for y in range(MAP_HEIGHT):
      for x in range(MAP_WIDTH):
        visible = libtcod.map_is_in_fov(fov_map, x, y)
        wall = map[x][y].block_sight
        if not visible:
          # It's out of the players field of view
          if map[x][y].explored:
            if wall:
              libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
            else:
              libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)

        else:
          # It's in the players field of view
          if wall:
            libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
          else:
            libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)

          map[x][y].explored = True

  for object in objects:
    if object != player:
      object.draw()
  player.draw()

  libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

  libtcod.console_set_default_background(panel, libtcod.black)
  libtcod.console_clear(panel)

  y = 1
  for (line, color) in game_msgs:
    libtcod.console_set_default_foreground(panel, color)
    libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
    y += 1

  render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
  render_bar(1, 5, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, libtcod.gray, libtcod.black)

  libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level: ' + str(dungeon_level))

  libtcod.console_set_default_foreground(panel, libtcod.white)
  libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

  libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def message(new_msg, color = libtcod.white):
  new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
  
  for line in new_msg_lines:
    if len(game_msgs) == MSG_HEIGHT:
      del game_msgs[0]

    game_msgs.append( (line, color) )

def msgbox(text, width = 50):
  menu(text, [], width)

def player_death(player):
  # game ends!
  global game_state
  message('You died!', libtcod.red)
  game_state  = 'dead'

  player.char = 'x'
  player.color = libtcod.dark_red

def projectile_death(projectile):
  
  projectile.char = ' '
  projectile.ai = None
  projectile.fighter = None
  projectile.send_to_back()

def monster_death(monster):
  # transform it into a corpse
  message(monster.name.capitalize() + ' is dead!', libtcod.orange)
  message(str(monster.fighter.xp) + ' experience points awarded!', libtcod.white)
  monster.char = 'x'
  monster.color = libtcod.dark_red
  monster.blocks = False
  monster.fighter = None
  monster.ai = None
  monster.name = 'remains of ' + monster.name
  monster.send_to_back()

def boss_death(monster):
  global stairs
  # transform it into a corpse
  message(monster.name.capitalize() + ' is dead!', libtcod.orange)
  message(str(monster.fighter.xp) + ' experience points awarded!', libtcod.white)
  monster.char = 'x'
  monster.color = libtcod.dark_red
  monster.blocks = False
  monster.fighter = None
  monster.ai = None
  monster.name = 'remains of ' + monster.name

  stairs = Object(monster.x, monster.y, 'V', 'Stairs', libtcod.white, blocks = False, always_visible = True)
  objects.append(stairs)
  stairs.send_to_back()
  monster.send_to_back()

    

def check_level_up():
  global level_up_xp

  level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR

  color = 0

  if player.fighter.xp >= level_up_xp:

    player.fighter.heal(player.fighter.max_hp/2)

    player.level += 1
    player.fighter.xp -= level_up_xp
    color += 50
    player.color = libtcod.Color(color, color, color)
    message('You can feel yourself growing stronger! You have reached level ' + str(player.level) + '!', libtcod.yellow)

    choice = None
    while choice == None:
      choice = menu('Level up! Choose a stat to raise:\n', ['Constitution (+20 HP)', 'Strength (+1 attack)', 'Toughness (+1 defense)'], LEVEL_SCREEN_WIDTH)

    if choice == 0:
      player.fighter.max_hp += 20

    elif choice == 1:
      player.fighter.power += 1

    elif choice == 2:
      player.fighter.defense += 1
  

##########################
# SPELLS AND TARGETING   #
##########################

def closest_monster(max_range):
  closest_enemy = None
  closest_dist = max_range + 1

  for object in objects:
    if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
      dist = player.distance_to(object)
      if dist < closest_dist:
        closest_enemy = object
        closest_dist = dist

  return closest_enemy

def line_of_sight(self, target):
  x = target.x - self.x
  y = target.y - self.y

  initial_distance = math.sqrt((x**2) + (y**2))

  deltax = int(round(x/initial_distance))
  deltay = int(round(y/initial_distance)) 
  
  dx, dy = 0, 0

  for t in range(int(round(initial_distance + 1))):
    if map[self.x + dx][self.y + dy].blocked:
      return False

    dx += deltax
    dy += deltay

  return True
     

def cast_heal():
  if player.fighter.hp == player.fighter.max_hp:
    message('You are already at full health!', libtcod.red)
    return 'cancelled'

  message('You feel your wounds begin to heal!', libtcod.fuchsia)
  message('You have regained ' + str(20 + 10 * player.level) + ' hit points!', libtcod.fuchsia)
  player.fighter.heal(20 + 10 * player.level)

def cast_confuse():
  monster = closest_monster(CONFUSE_RANGE)

  if monster is None:
    message('No enemy is close enough to confuse!', libtcod.red)
    return 'cancelled'

  old_ai = monster.ai
  monster.ai = ConfusedMonster(old_ai)
  monster.ai.owner = monster
  message('The eyes of the ' + monster.name + ' look vacant as it starts to stumble around!', libtcod.sepia)

def cast_lightning():
  monster = closest_monster(LIGHTNING_RANGE)

  if monster is None:
    message('No enemies are close enough to hit with lightning!', libtcod.red)
    return 'cancelled'

  message('The ' + monster.name + ' jolts as electricity courses through it!', libtcod.dark_violet)
  monster.fighter.take_damage(LIGHTNING_DAMAGE + 10 * player.level)

def cast_fireball(starting_x, starting_y, target_x, target_y):
  
  ai_component = Projectile(target_x, target_y)
  fighter_component = Fighter(hp = 1, defense = 100, power = 5, xp = 0, death_function = projectile_death)
  projectile = Object(starting_x, starting_y, '*', 'Fireball', libtcod.desaturated_red, blocks = False, always_visible = False, fighter = fighter_component, ai = ai_component)
 
  
def cast_lifesteal():
  monster = closest_monster(LIFESTEAL_RANGE)

  if monster is None:
    message('No enemy is close enough to steal life from!', libtcod.red)
    return 'cancelled'

  message("The " + monster.name + " begins to quiver as it's lifeforce is drained!", libtcod.dark_crimson)
  monster.fighter.take_damage(LIFESTEAL_DAMAGE + 10 * player.level)
  player.fighter.heal(LIFESTEAL_DAMAGE + 10 * player.level)

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
  bar_width = int(float(value) / maximum * total_width)

  libtcod.console_set_default_background(panel, back_color)
  libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

  libtcod.console_set_default_background(panel, bar_color)
  if bar_width > 0:
    libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

  libtcod.console_set_default_foreground(panel, libtcod.white)
  libtcod.console_print_ex(panel, x + total_width/2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def get_names_under_mouse():
  global mouse

  (x, y) = (mouse.cx, mouse.cy)

  names = [object.name for object in objects if object.x == x and object.y == y and libtcod.map_is_in_fov(fov_map, object.x, object.y)]

  names = ', '.join(names)
  return names.capitalize()

def menu(header, options, width):
  if len(options)> 26: raise ValueError('Cannot have a menu with more than 26 options.')
 
  # Calculate height for the header (after auto-wrap) and one line per option
  header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
  if header == '':
    header_height = 0

  height = len(options) + header_height

  # Create an off-screen console that represents the menu's window
  window = libtcod.console_new(width, height)
  
  # Print the header with auto wrap
  libtcod.console_set_default_foreground(window, libtcod.white)
  libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

  # print all the options
  y = header_height
  letter_index = ord('a')
  for option_text in options:
    text = '(' + chr(letter_index) + ')' + option_text
    libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
    y += 1
    letter_index += 1

  # blit the contents of 'window' to the root console
  x = SCREEN_WIDTH/2 - width/2
  y = SCREEN_HEIGHT/2 - height/2

  libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

  # present the root console to player and wait for them to take action
  libtcod.console_flush()
  key = libtcod.console_wait_for_keypress(True)

  if key.vk == libtcod.KEY_ENTER and key.lalt:
    libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

  # convert the ASCII code to an index, if it corresponds to an option, return it
  index = key.c - ord('a')
  if index >= 0 and index < len(options): return index
  return None

def inventory_menu(header):

  if len(inventory) == 0:
    options = ['Inventory is empty']
  else:
    options = [item.name for item in inventory]

  index = menu(header, options, INVENTORY_WIDTH)

  # if an item was chosen, return it
  if index is None or len(inventory) == 0: return None
  return inventory[index].item

def new_game():
  global player, inventory, game_msgs, game_state, dungeon_level

  fighter_component = Fighter(hp = 100, defense = 2, power = 5, xp = 0, death_function = player_death)
  player = Object(0, 0, 'O', 'player', libtcod.Color(0, 0, 0), blocks=True, fighter = fighter_component)

  player.level = 1

  dungeon_level = 1

  make_map()
  initialize_fov()
  
  game_state = 'playing'
  inventory= []

  game_msgs = []

  message("Welcome Stranger! Prepare to battle with the Aliens of Nar'Gyl!", libtcod.red)

def play_game():
  global key, mouse

  player_action = None

  mouse = libtcod.Mouse()
  key = libtcod.Key()

  while not libtcod.console_is_window_closed():

    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
    render_all()  
  
    libtcod.console_flush()

    check_level_up()

    for object in objects:
      object.clear()
  
    player_action = handle_keys()
    if player_action == 'exit':
      save_game()
      break

    if game_state == 'playing' and player_action != 'didnt-take-turn':
      for object in objects:
        if object.ai:
          object.ai.take_turn()

def save_game():
  file = shelve.open('savegame', 'n')
  file['map'] = map
  file['objects'] = objects
  file['player_index'] = objects.index(player)
  file['stairs_index'] = objects.index(stairs)
  file['dungeon_level'] = dungeon_level
  file['inventory'] = inventory
  file['game_msgs'] = game_msgs
  file['game_state'] = game_state
  file.close()

def load_game():
  global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

  file = shelve.open('savegame', 'r')
  map = file['map']
  objects = file['objects']
  player = objects[file['player_index']]
  stairs = objects[file['stairs_index']]
  dungeon_level = file['dungeon_level']
  inventory = file['inventory']
  game_msgs = file['game_msgs']
  game_state = file['game_state']
  file.close()

  initialize_fov()
  
def main_menu():

  img = libtcod.image_load('my_menu_background.png')

  while not libtcod.console_is_window_closed():
    libtcod.image_blit_2x(img, 200, 200, 200)

    libtcod.console_set_default_foreground(0, libtcod.light_yellow)
    libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 4, libtcod.BKGND_NONE, libtcod.CENTER, "MINES OF NAR'GYL")
    libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT -2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Kyle')

    choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

    if choice == 0:
      new_game()
      play_game()

    if choice == 1:
      try:
        load_game()
      except:
        msgbox('\nNo Saved game to load.\n', 24)

    elif choice == 2:
      break

####################################
# System Initialization
###################################

libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, "Mines of Nar'Gyl", False)
libtcod.sys_set_fps(LIMIT_FPS)

con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()
  

