#!/usr/bin/env python3
import logging
import os
import sys
from io import BytesIO
from typing import Dict, Optional, Tuple

import click
import requests
import structlog
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL.ImageFont import FreeTypeFont
from reportlab.graphics import renderPM
from reportlab.graphics.shapes import Drawing
from structlog.typing import FilteringBoundLogger
from svglib.svglib import svg2rlg


class THMBadgeGenerator:
  __username: str
  __log: FilteringBoundLogger
  __image: Image.Image
  __draw: ImageDraw.ImageDraw
  __image_dest_path: str
  __scale: float

  def __init__(self, log_level: str, username: str, image_dest_path: str) -> None:

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
    )
    self.__log = structlog.get_logger()
    self.__username = username
    self.__image_dest_path = image_dest_path

    self.__log.debug('starting THMProfileScraper with')
    self.__log.debug(f'username: {username}')
    self.__log.debug(f'log_level: {log_level}')

  def __scale_value(self, val: int):
    return int(val * self.__scale)

  def __fetch_profile(self, username: str) -> Optional[Dict[str, str]]:
    self.__log.info(f'fetching profile for {username}')
    url = f'https://tryhackme.com/api/v2/public-profile?username={username}'

    try:
      response = requests.get(url)
      response.raise_for_status()
      data = response.json()

      if data.get('status') == 'success':
        return data.get('data')
      else:
        self.__log.critical(f'Error: {data.get('message', 'Unknown error')}')
        sys.exit(4)
    except requests.exceptions.RequestException as e:
      self.__log.critical(f'Request failed: {e}')
      sys.exit(4)

  def __generate_badge(self, profile: Dict[str, str]) -> None:
    self.__log.info('Generating badge')

    # --- Configuration ---
    self.__scale = 1

    width, height = self.__scale_value(350), self.__scale_value(180)
    bg_color = (20, 29, 45)  # Deep THM Blue
    card_color = (30, 42, 60)  # Slightly lighter Blue
    accent_green = (120, 230, 100)  # Vibrant Green
    accent_white = (255, 255, 255)
    accent_grey = (160, 174, 192)
    accent_red = (255, 0, 0)
    accent_cyan = (0, 255, 255)
    accent_yellow = (255, 255, 0)
    accent_brown = (255, 165, 0)
    accent_pink = (255, 0, 255)

    # Prepare image
    self.__image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    self.__draw = ImageDraw.Draw(self.__image)

    self.__draw_corners(bg_color, card_color, height, width)

    # --- Typography (Attempt to use system fonts, fallback to default) ---
    name_font, stat_label_font, stat_value_font = self.__load_fonts()

    # --- Header Content ---
    self.__render_thm_logo()

    # --- Avatar ---
    self.__render_avatar(accent_green, name_font, profile, width)

    self.__draw.text((width - self.__scale_value(20), self.__scale_value(15)), profile.get('username', ''),
                     font=name_font, fill=accent_white, anchor="ra")

    # --- Stats Grid ---
    stats_data = [
        (
            'Level',
            self.__get_level_name(int(profile.get('level'))),
            accent_red,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/shield-alt.svg'
        ),
        (
            'Rank',
            f'#{profile.get("rank")}',
            accent_pink,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/trophy.svg'),
        (
            'Points',
            f'{int(profile.get("totalPoints", 0)):,}',
            accent_yellow,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/bolt.svg'),
        (
            'Top',
            f'{profile.get("topPercentage")}%',
            accent_green,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/globe.svg'),
        (
            'Streak',
            f'{profile.get("streak")} days',
            accent_cyan,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/fire.svg'),
        (
            'Rooms',
            str(profile.get('completedRoomsNumber')),
            accent_brown,
            'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/cube.svg'),
    ]

    # 2x3 Grid Layout
    cols = 3
    cell_width = (width - self.__scale_value(40)) // cols
    cell_height = self.__scale_value(45)

    for i, (label, value, color, icon_url) in enumerate(stats_data):
      row = i // cols
      col = i % cols
      x = self.__scale_value(20) + col * cell_width
      y = self.__scale_value(70) + row * cell_height

      # Render Icon
      try:
        response = requests.get(icon_url)
        if response.status_code == 200:
          drawing: Drawing = svg2rlg(BytesIO(response.content))
          icon_bytes = BytesIO()
          renderPM.drawToFile(drawing, icon_bytes, fmt='PNG', bg=0xffffff)
          icon_bytes.seek(0)

          icon_mask = ImageOps.invert(Image.open(icon_bytes).convert("L"))
          icon_img = Image.new('RGBA', icon_mask.size, color + (255,))
          icon_img.putalpha(icon_mask)

          # Resize icon
          icon_h = self.__scale_value(16)
          icon_aspect = icon_img.width / icon_img.height
          icon_w = int(icon_h * icon_aspect)
          icon_img = icon_img.resize((icon_w, icon_h), Image.Resampling.LANCZOS)

          self.__image.paste(icon_img, (x, y + self.__scale_value(1)), icon_img)
          text_offset = icon_w + self.__scale_value(10)
        else:
          text_offset = 0
      except Exception as e:
        self.__log.warning(f'Failed to load icon for {label}: {e}')
        text_offset = 0

      self.__draw.text((x + text_offset, y), label.upper(), font=stat_label_font, fill=accent_grey)
      self.__draw.text((x + text_offset, y + self.__scale_value(18)), value, font=stat_value_font,
                       fill=accent_green)

    # Save the image
    self.__save_the_image()

  def __save_the_image(self):
    output_path = os.path.join(os.getcwd(), 'tryHackMe.png')
    if os.path.basename(os.getcwd()) == 'script':
      output_path = os.path.join(os.path.dirname(os.getcwd()), 'tryHackMe.png')

    self.__image.save(output_path)
    self.__log.info(f'Saving badge to {output_path}')

  def __get_level_name(self, level: int) -> str:
    level_names = {
        1 : '[0x1-Neophyte]',
        2 : '[0x2-Apprentice]',
        3 : '[0x3-Pathfinder]',
        4 : '[0x4-Seeker]',
        5 : '[0x5-Visionary]',
        6 : '[0x6-Voyager]',
        7 : '[0x7-Adept]',
        8 : '[0x8-Hacker]',
        9 : '[0x9-Mage]',
        10: '[0xA-Wizard]',
        11: '[0xB-Master]',
        12: '[0xC-Guru]',
        13: '[0xD-Legend]',
        14: '[0xE-Gardian]',
        15: '[0xF-TITAN]',
        16: '[0x10-SAGE]',
        17: '[0x11-VANGUARD]',
        18: '[0x12-SHOGUN]',
        19: '[0x13-ASCENDED]',
        20: '[0x14-MYTHIC]',
        21: '[0x15-GRANDMASTER]'
    }
    return level_names[level]

  def __draw_corners(self, bg_color: tuple[int, int, int], card_color: tuple[int, int, int], height: int, width: int):

    # Draw main card background with rounded corners
    radius = self.__scale_value(15)
    self.__draw.rounded_rectangle([0, 0, width, height], radius=radius, fill=bg_color)

    # Draw header section with a different color/shade
    header_height = self.__scale_value(50)
    self.__draw.rounded_rectangle([0, 0, width, header_height], radius=radius, fill=card_color)
    self.__draw.rectangle([0, header_height - radius, width, header_height],
                          fill=card_color)  # Flatten bottom corners of header

  def __render_avatar(self,
                      color_accent: tuple[int, int, int],
                      name_font: FreeTypeFont, profile: dict[str, str], width: int):

    avatar_url = profile.get('avatar')
    if avatar_url:
      try:
        response = requests.get(avatar_url)
        if response.status_code == 200:
          avatar_img = Image.open(BytesIO(response.content)).convert('RGBA')

          # Resize and make it circular
          avatar_size = (self.__scale_value(36), self.__scale_value(36))
          avatar_img = avatar_img.resize(avatar_size, Image.Resampling.LANCZOS)

          mask = Image.new('L', avatar_size, 0)
          mask_draw = ImageDraw.Draw(mask)
          mask_draw.ellipse((0, 0) + avatar_size, fill=255)

          # Background circle for avatar (border effect)
          # We want the avatar to be close to the username, which is right-aligned
          # Username ends at width - 20 * scale.
          # Calculate text width to place avatar before it
          try:
            text_bbox = self.__draw.textbbox((0, 0), profile.get('username', ''), font=name_font)
            text_width = text_bbox[2] - text_bbox[0]
          except Exception as e:
            self.__log.warn(f'Failed to set avatar text: {e}')
            self.__log.info('Fallback to default size text: 100')
            text_width = self.__scale_value(100)

          avatar_x = width - self.__scale_value(20) - text_width - self.__scale_value(10) - avatar_size[0]
          avatar_y = self.__scale_value(7)
          border = max(1, self.__scale_value(2))
          self.__draw.ellipse(
              (
                  avatar_x - border,
                  avatar_y - border,
                  avatar_x + avatar_size[0] + border,
                  avatar_y + avatar_size[1] + border
              ),
              fill=color_accent)

          self.__image.paste(avatar_img, (avatar_x, avatar_y), mask)
      except Exception as e:
        self.__log.warn(f'Failed to load avatar: {e}')

  def __render_thm_logo(self):

    # Official Logo
    logo_url = "https://assets.tryhackme.com/img/logo/tryhackme_logo_full.svg"
    try:
      response = requests.get(logo_url)
      if response.status_code == 200:
        # Convert SVG to Drawing object
        drawing: Drawing = svg2rlg(BytesIO(response.content))

        if drawing:
          # Render Drawing object to PNG in memory (on black background to use as mask)
          logo_bytes = BytesIO()
          renderPM.drawToFile(drawing, logo_bytes, fmt='PNG', bg=0x000000)
          logo_bytes.seek(0)

          # Use the luminance as a mask for a solid white color to get transparency
          logo_mask = Image.open(logo_bytes).convert('L')
          logo_img = Image.new('RGBA', logo_mask.size, (255, 255, 255, 255))
          logo_img.putalpha(logo_mask)

          # Resize logo to fit header
          logo_h = self.__scale_value(28)
          logo_aspect = logo_img.width / logo_img.height
          logo_w = int(logo_h * logo_aspect)
          logo_img = logo_img.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

          self.__image.paste(logo_img, (self.__scale_value(20), self.__scale_value(11)), logo_img)
        else:
          self.__log.warn('Failed to load official logo')
    except Exception as e:
      self.__log.warn(f'Failed to load official logo: {e}')

  def __load_fonts(self) -> Tuple[FreeTypeFont, FreeTypeFont, FreeTypeFont]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(script_dir, 'fonts', 'FiraCode-Regular.ttf')
    try:
      name_font = ImageFont.truetype(font_path, self.__scale_value(20))
      stat_label_font = ImageFont.truetype(font_path, self.__scale_value(14))
      stat_value_font = ImageFont.truetype(font_path, self.__scale_value(14))
    except Exception:
      name_font = ImageFont.load_default()
      stat_label_font = ImageFont.load_default()
      stat_value_font = ImageFont.load_default()
    return name_font, stat_label_font, stat_value_font

  def run(self) -> None:
    self.__log.info('Generating THM badge')
    profile = self.__fetch_profile(self.__username)

    if profile:
      self.__log.info(f"--- TryHackMe Profile Header: {profile.get('username')} ---")
      self.__log.info(f'Level:      {profile.get("level")}')
      self.__log.info(f'Rank:       {profile.get("rank")}')
      self.__log.info(f'Points:     {profile.get("totalPoints")}')
      self.__log.info(f'Rooms:      {profile.get("completedRoomsNumber")}')
      self.__log.info(f'Badges:     {profile.get("badgesNumber")}')
      self.__log.info(f'Streak:     {profile.get("streak")} days')
      self.__log.info(f'Top:        {profile.get("topPercentage")} %')
      self.__log.info(f'Country:    {profile.get("country")}')
      self.__log.info(f'Avatar:     {profile.get("avatar")}')
      self.__log.info(f'username:   {self.__username}')

      self.__generate_badge(profile)


@click.command()
@click.option(
    '--log_level', default='INFO',
    help='set the logger level, choose between [CRITICAL / ERROR / WARNING / INFO / '
         'DEBUG]', show_default=True)
@click.option('--image_dest_path', default='../tryHackMe.png', help='path to save the badge image')
@click.argument('username', type=click.STRING)
def command_line(log_level: str, username: str, image_dest_path: str) -> None:
  """
  THM profile scraper.\n
  USERNAME = THM profile username. \n
  usage: \n
  python generate_thm_badge.py <username> --log_level <level>
  """

  print(f'=== Start {THMBadgeGenerator.__name__} ===')
  runner = THMBadgeGenerator(log_level, username, image_dest_path)
  runner.run()
  print(f'=== End {THMBadgeGenerator.__name__} ===')


if __name__ == "__main__":
  command_line()
