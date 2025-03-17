from typing import List, Optional

from sqlalchemy import CHAR, DECIMAL, Date, ForeignKeyConstraint, Index, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal

class Base(DeclarativeBase):
    pass


class ExchangeRates(Base):
    __tablename__ = 'exchange_rates'
    __table_args__ = (
        Index('currency_code', 'currency_code', unique=True),
    )

    rate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    currency_code: Mapped[str] = mapped_column(String(10))
    currency_name: Mapped[str] = mapped_column(String(50))
    currency_symbol: Mapped[str] = mapped_column(String(5))
    exchange_rate: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 6))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))


class WebsiteStats(Base):
    __tablename__ = 'website_stats'

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    total_visitors: Mapped[Optional[int]] = mapped_column(INTEGER(11), server_default=text('0'))
    daily_visitors: Mapped[Optional[int]] = mapped_column(INTEGER(11), server_default=text('0'))


class YoutubeUsers(Base):
    __tablename__ = 'youtube_users'

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))
    user_avatar: Mapped[Optional[str]] = mapped_column(String(512))
    channel_url: Mapped[Optional[str]] = mapped_column(String(512))

    youtube_super_thanks: Mapped[List['YoutubeSuperThanks']] = relationship('YoutubeSuperThanks', back_populates='user')


class YoutubeVideos(Base):
    __tablename__ = 'youtube_videos'
    __table_args__ = (
        Index('youtube_video_id', 'youtube_video_id', unique=True),
    )

    video_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    youtube_video_id: Mapped[str] = mapped_column(String(20))
    video_title: Mapped[str] = mapped_column(String(255))
    video_url: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))


class YoutubeSuperThanks(Base):
    __tablename__ = 'youtube_super_thanks'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['youtube_users.user_id'], ondelete='CASCADE', name='youtube_super_thanks_ibfk_1'),
        Index('rate_id', 'rate_id'),
        Index('user_id', 'user_id'),
        Index('video_id', 'video_id')
    )

    thanks_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36))
    video_id: Mapped[str] = mapped_column(String(36))
    amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    full_amount_text: Mapped[str] = mapped_column(String(255))
    recorded_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))
    rate_id: Mapped[Optional[str]] = mapped_column(CHAR(36))
    currency_code: Mapped[Optional[str]] = mapped_column(String(10))
    message: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped['YoutubeUsers'] = relationship('YoutubeUsers', back_populates='youtube_super_thanks')
