#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
import time
import pypyodbc as pyodbc
import datetime
import pydeck as pdk
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import Image
from requests_html import HTMLSession
import locale
import folium
import base64

from sys import platform

if platform == "linux" or platform == "linux2":
    # linux
    SQL_DRIVER = 'SQL Server'
elif platform == "darwin":
    # OS X
    SQL_DRIVER = 'ODBC Driver 17 for SQL Server'

elif platform == "win32":
    # Windows...
    SQL_DRIVER = 'ODBC Driver 17 for SQL Server'
    SQL_DRIVER = 'SQL Server'

from Visualization import GenerateGeo, GenerateGeoAnimation


#####################################################
# SQL query functions
#####################################################
# @st.cache(allow_output_mutation=True)
def getDatabaseConnection():
    return pyodbc.connect(
        f'DRIVER={SQL_DRIVER};SERVER=*.*.*.*;DATABASE=RealTimeLoopData;UID=*;PWD=*')


@st.cache
def getLoopDetectorLocation():
    conn = getDatabaseConnection()

    SQL_Query = pd.read_sql_query(
        '''	SELECT Distinct [CabName]
              ,cab.[Lat]
              ,cab.[Lon]
          FROM [RealTimeLoopData].[dbo].[cabinets] as cab join [RealTimeLoopData].[dbo].[MinuteDataDefnNW] as def on cab.UnitName = def.id
          WHERE SUBSTRING(def.id, 12, 2) = '_M' AND (SUBSTRING(def.id, 15, 3) = '___' OR SUBSTRING(def.id, 15, 3) = 'H__')
          AND def.[covered_dist] > 0 AND def.[covered_dist] <= 2
          AND [CabName] IS NOT NULL AND cab.[Lat] IS NOT NULL''', conn)

    return pd.DataFrame(SQL_Query)


def getTrafficIndex(date):
    conn = getDatabaseConnection()

    SQL_Query = pd.read_sql_query(
        '''SELECT DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) as [time]
          , AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
          , AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
          , AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
          , AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
          , AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
          , AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
      FROM [RealTimeLoopData].[dbo].[TrafficIndex]
      WHERE CAST([time] AS DATE) = ?
      GROUP BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) 
      ORDER BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) 
      ''', conn, params=[date])

    return pd.DataFrame(SQL_Query)


def getTrafficIndexMultiDays(sdate, edate):
    conn = getDatabaseConnection()

    SQL_Query = pd.read_sql_query(
        '''SELECT DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) as [time]
          , AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
          , AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
          , AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
          , AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
          , AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
          , AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
      FROM [RealTimeLoopData].[dbo].[TrafficIndex]
      WHERE time between ? and ?
      GROUP BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) 
      ORDER BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0)
      ''', conn, params=[sdate, edate])

    return pd.DataFrame(SQL_Query)


def getDailyIndex(sdate, edate):
    conn = getDatabaseConnection()
    SQL_Query = pd.read_sql_query(
        '''	SELECT convert(varchar, CAST([time] AS DATE), 107) as Date, AVG([TrafficIndex_GP]) as daily_index_GP, AVG([TrafficIndex_HOV]) as daily_index_HOV
        FROM [RealTimeLoopData].[dbo].[TrafficIndex]
        WHERE CAST([time] AS DATE) BETWEEN ? AND ?
            AND ( (DATEPART(HOUR, [time]) >= 6 AND DATEPART(HOUR, [time]) <= 9) OR (DATEPART(HOUR, [time]) >= 15 and DATEPART(HOUR, [time]) <= 18) )
        GROUP BY CAST([time] AS DATE)
        ORDER BY CAST([time] AS DATE)
        ''', conn, params=[sdate, edate])
    return pd.DataFrame(SQL_Query)


def getSegments():
    conn = getDatabaseConnection()
    SQL_Query = pd.read_sql_query(
        '''	SELECT *
          FROM [RealTimeLoopData].[dbo].[Segments]''', conn)
    return pd.DataFrame(SQL_Query)


def getSegmentTPS_Day(sdate, edate, segmentID):
    conn = getDatabaseConnection()
    SQL_Query = pd.read_sql_query(
        '''	SELECT CONVERT(varchar, CAST([time] AS DATE), 107) as [time]
              ,AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
              ,AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
              ,AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
              ,AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
              ,AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
              ,AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
        FROM [RealTimeLoopData].[dbo].[SegmentTrafficIndex]
        WHERE [time] BETWEEN ? and ?
        AND [segmentID] = ?
        GROUP BY CAST([time] AS DATE)
        ORDER BY CAST([time] AS DATE)
        ''', conn, params=[sdate, edate, segmentID])
    return pd.DataFrame(SQL_Query)


# Zhiyong to confirm whether this is a no-use code clip
# def getSegmentTPS_5Min(sdate, edate, segmentID):
# 	conn = getDatabaseConnection()
# 	SQL_Query = pd.read_sql_query(
# 	'''	SELECT DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) as [time]
# 		      ,AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
# 		      ,AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
# 		      ,AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
# 		      ,AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
# 		      ,AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
# 		      ,AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
# 		FROM [RealTimeLoopData].[dbo].[SegmentTrafficIndex]
# 		WHERE [time] BETWEEN ? and ?
# 		AND [segmentID] = ?
# 		GROUP BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0)
# 		ORDER BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0)
# 		''', conn, params = [sdate, edate, segmentID])
# 	return pd.DataFrame(SQL_Query)

def getSegmentTPS_5Min(sdate, edate):
    conn = getDatabaseConnection()
    SQL_Query = pd.read_sql_query(
        '''	SELECT DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0) as [time]
                ,[segmentID]
                ,AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
                ,AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
                ,AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
                ,AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
                ,AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
                ,AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
        FROM [RealTimeLoopData].[dbo].[SegmentTrafficIndex]
        WHERE [time] BETWEEN ? and ?
        GROUP BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0),[segmentID]
        ORDER BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/5*5, 0),[segmentID]
        ''', conn, params=[sdate, edate])
    return pd.DataFrame(SQL_Query)


def getSegmentTPS_1Hour(sdate, edate):
    conn = getDatabaseConnection()
    SQL_Query = pd.read_sql_query(
        '''	SELECT DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/60*60, 0) as [time]
                ,[segmentID]
                ,AVG([AVG_Spd_GP]) AS [AVG_Spd_GP]
                ,AVG([AVG_Spd_HOV]) AS [AVG_Spd_HOV]
                ,AVG([AVG_Vol_GP]) AS [AVG_Vol_GP]
                ,AVG([AVG_Vol_HOV]) AS [AVG_Vol_HOV]
                ,AVG([TrafficIndex_GP]) AS [TrafficIndex_GP]
                ,AVG([TrafficIndex_HOV]) AS [TrafficIndex_HOV]
        FROM [RealTimeLoopData].[dbo].[SegmentTrafficIndex]
        WHERE [time] BETWEEN ? and ?
        GROUP BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/60*60, 0),[segmentID]
        ORDER BY DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [time])/60*60, 0),[segmentID]
        ''', conn, params=[sdate, edate])
    return pd.DataFrame(SQL_Query)


def getMorningPeakVolume(sdate, edate):
    conn = getDatabaseConnection()

    SQL_Query = pd.read_sql_query(
        '''	SELECT convert(varchar, CAST([time] AS DATE), 107) as Date, AVG(AVG_Vol_GP) as AVG_Vol_GP, AVG(AVG_Vol_HOV) as AVG_Vol_HOV
        FROM [RealTimeLoopData].[dbo].[TrafficIndex]
        WHERE CAST([time] AS DATE) between ? and ?
            AND DATEPART(HOUR, [time]) >= 6 AND DATEPART(HOUR, [time]) <= 9
        GROUP BY CAST([time] AS DATE)
        ORDER BY CAST([time] AS DATE)
        ''', conn, params=[sdate, edate])

    return pd.DataFrame(SQL_Query)


def getEveningPeakVolume(sdate, edate):
    conn = getDatabaseConnection()

    SQL_Query = pd.read_sql_query(
        '''	SELECT convert(varchar, CAST([time] AS DATE), 107) as Date, AVG(AVG_Vol_GP) as AVG_Vol_GP, AVG(AVG_Vol_HOV) as AVG_Vol_HOV
        FROM [RealTimeLoopData].[dbo].[TrafficIndex]
        WHERE CAST([time] AS DATE) between ? and ?
            AND DATEPART(HOUR, [time]) >= 15 and DATEPART(HOUR, [time]) <= 18
        GROUP BY CAST([time] AS DATE)
        ORDER BY CAST([time] AS DATE)
        ''', conn, params=[sdate, edate])

    return pd.DataFrame(SQL_Query)


def getCOVID19Info():
    return pd.read_csv('Washington_COVID_Cases.csv')


#####################################################
# display functions
#####################################################

def IntroduceTrafficIndex():
    ###########
    # Sidebar #
    ###########
    # st.sidebar.markdown("## Components")
    # st.sidebar.checkbox("Data Course")
    # st.sidebar.checkbox("Traffic Performance Score Caculation")
    ###########
    # Content #
    ###########
    st.markdown("# Traffic Performance Score in Seattle Area")
    st.markdown("## Introduction to Traffic Performance Score")
    st.markdown(
        "Traffic Performance Score (TPS) can intuitively indicate the overall performance of urban traffic networks. "
        "In this website, the TPS is calculated and visualized to quantify the overall traffic condition in the Seattle area. "
        "With this website, you can view "
        "\n * The TPS with different temporal resolutions, ranging from one minute to one day. "
        "\n * The TPS of general purpose (GP) and HOV lanes. "
        "\n * Impact of COVID-19 on urban traffic reflected by the TPS. "
        "\n * Other traffic performance metrics. ")

    st.markdown("To view more information, please select on the left navigation panel. Enjoy! :sunglasses:")

    #################################################################
    st.markdown("## Traffic Performance Score")

    st.markdown("### Segment-baed TPS Map")

    date = st.date_input('Pick a date', value=datetime.datetime.now().date())
    datatime1 = datetime.datetime.combine(date, datetime.time(00, 00))
    datatime2 = datetime.datetime.combine(date, datetime.time(23, 59))

    df_SegTPS = getSegmentTPS_1Hour(datatime1, datatime2)
    df_SegTPS.columns = ['time', 'segmentID', 'AVG_Spd_GP', 'AVG_Spd_HOV', 'AVG_Vol_GP', 'AVG_Vol_HOV',
                         'TrafficIndex_GP', 'TrafficIndex_HOV']

    GenerateGeoAnimation(df_SegTPS)

    st.markdown("### Variation of Daily Network-wide TPS")

    # date = st.date_input('Please select a date', datetime.datetime.now().date())
    # date = datetime.datetime.now().date()
    df_TI = getTrafficIndex(date)

    # remove outliers from HOV traffic index
    df_TI.loc[df_TI['avg_vol_hov'] == 0, 'trafficindex_hov'] = 1.0

    df_TI['trafficindex_gp'] = df_TI['trafficindex_gp'] * 100
    # df_TI['trafficindex_gp'] = df_TI['trafficindex_gp'].astype('int64')
    df_TI['trafficindex_hov'] = df_TI['trafficindex_hov'] * 100
    # df_TI['trafficindex_hov'] = df_TI['trafficindex_hov'].astype('int64')

    # df_TI['trafficindex_gp'] = df_TI['trafficindex_gp'] * 65
    # st.line_chart(df_TI[['trafficindex_gp', 'avg_spd_gp']])

    sampling_interval = 1
    data = df_TI.loc[::sampling_interval, ['time', 'trafficindex_gp', 'trafficindex_hov']]
    lw = 1  # line width
    # Create traces
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data['time'], y=data['trafficindex_gp'],
                             mode='lines', line=dict(dash='solid', width=lw),
                             name='Main lane'))

    fig.add_trace(go.Scatter(x=data['time'], y=data['trafficindex_hov'],
                             mode='lines', line=dict(dash='solid', width=lw),
                             name='HOV lane'))

    fig.update_layout(xaxis_title='Time', yaxis_title='Traffic Performance Score (%)',
                      legend=dict(x=.01, y=0.05),
                      margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4), width=700, height=450)

    # fig.update_yaxes(range=[0, 1.1])

    # st.write('Traffic Performance Score of (', date, '):')

    st.plotly_chart(fig)

    # dataFields = st.multiselect('Show Data',  list(df_TI.columns.values), default = ['time', 'trafficindex_gp', 'trafficindex_hov'] )
    # st.write(df_TI[dataFields])

    #################################################################
    st.markdown("## Data Source")
    st.markdown(
        "The TPS is calculated based on data collected from more than 44800 inductive loop detectors deployed on freeways in Seattle, WA area. "
        "Freeways include: I-5, I-90, I-99, I-167, I-405, and SR-520. The raw data comes from Washington State Department of Transportation (WSDOT). "
        "Representative detectors are shown in the following map. ")
    showLoopDetectorMap()

    #################################################################
    st.markdown("## Traffic Performance Score Calculation")
    st.markdown(
        "The raw data contains lane-wise **S**peed, **V**olume, and **O**ccupancy information collected by each loop detector. "
        "Each detector's meta data includes detector category, route, milepost, director, direction, address. "
        "Based on the consecutive detectors' location information, we separate the freeways into segments, "
        "each of which only contains one loop detector per lane. We consider a road segment's length is the corresponding detector's covered length. "
        "The time interval of the data is one-minute. ")
    st.markdown("The **Traffic Performance Score** (**TPS**) at time $t$ is calculated using the following equation:")
    st.latex(r'''
        \text{TPS}_t = \frac{\displaystyle\sum_{i=1}^n S_t^i * V_t^i * D_t^i }{ \displaystyle\sum_{i=1}^n V_t^i * D_t^i * 65 } * 100\%
        ''')
    st.markdown("where $S_t^i$, $V_t^i$, and $D_t^i$ represent the **S**peed, **V**olume, covered **D**istance "
                "of each road segment $i$ at time $t$, respectively. "
                "The unit of speed is mile per hour (mph), and we set 65 as the upper limit of the speed. "
                "The unit of covered distance is mile.")
    st.markdown("In this way, the **TPS** is a value ranges from 0 to 1.0 ($TPS \in [0,1.0]$). "
                "The closer to one the **TPS** is, the better the overall network-wide traffic condition is. ")


def showTrafficIndex():
    ###########
    # Sidebar #
    ###########
    # st.sidebar.markdown("## Components")

    # index = st.sidebar.radio( "Display:", ("Daily Index", "Traffic Performance Score per Minute", "Tabular Data"))
    # daily_Index = st.sidebar.checkbox("Daily Index", value = True)
    # minute_Index = st.sidebar.checkbox("Traffic Performance Score per Minute")
    # tablular_Data = st.sidebar.checkbox("Tabular Data")
    daily_Index, five_minute_Index, tablular_Data = True, True, True
    ########################
    # main content
    ########################
    st.markdown("# Network-based Traffic Performance Score")
    st.markdown("In this section, the temporal dynamic of network-wide traffic changes is interactively demonstrated"
                "by visualizing the TPS of different types of lanes with various time resolutions, ranging from 5 minutes to one day."
                "the TPS is provided based on selected start and end dates.")
    # "You can check or uncheck the checkbox in the left panel to adjuect the displayed information.")
    # sdate = st.date_input('Pick a start date', value = (datetime.datetime.now() - datetime.timedelta(days=30)))
    # edate = st.date_input('Pick an end date', value = datetime.datetime.now().date())
    # st.write('From ',sdate, ' to ', edate,':')

    ########################
    # Daily Traffic Performance Score #
    ########################

    if daily_Index:
        st.markdown("## Daily Traffic Performance Score")
        st.markdown("the daily dynamic of network-wide traffic changes is interactively demonstrated"
                    "by visualizing the TPS of two types of lanes(Main lane and HOV lane)."
                    "The mouse slides on the curve to flash the daily TPS data."
                    "Slide the mouse to the upper right corner to display the interactive toolbar")

        sdate_DI = st.date_input('Select a start date for Daily Traffic Performance Score',
                                 value=(datetime.datetime.now() - datetime.timedelta(days=90)))
        edate_DI = st.date_input('Select an end date for Daily Traffic Performance Score',
                                 value=datetime.datetime.now().date())
        st.write('From ', sdate_DI, ' to ', edate_DI, ':')

        df_DailyIndex = getDailyIndex(sdate_DI, edate_DI)

        df_DailyIndex['date'] = df_DailyIndex['date'].astype('datetime64[ns]')
        df_DailyIndex['date'] = df_DailyIndex['date'].dt.date

        df_DailyIndex['daily_index_gp'] = df_DailyIndex['daily_index_gp'] * 100
        # df_DailyIndex['daily_index_gp'] = df_DailyIndex['daily_index_gp'].astype('int64')
        df_DailyIndex['daily_index_hov'] = df_DailyIndex['daily_index_hov'] * 100
        # df_DailyIndex['daily_index_hov'] = df_DailyIndex['daily_index_hov'].astype('int64')

        data = df_DailyIndex[['date', 'daily_index_gp', 'daily_index_hov']]
        lw = 1  # line width
        # Create traces
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data['date'], y=data['daily_index_gp'],
                                 mode='lines', line=dict(dash='solid', width=lw),
                                 name='Main lane'))
        fig.add_trace(go.Scatter(x=data['date'], y=data['daily_index_hov'],
                                 mode='lines', line=dict(dash='solid', width=lw),
                                 name='HOV lane'))
        fig.update_layout(xaxis_title='Date', yaxis_title='Traffic Performance Score (%)',
                          legend=dict(x=.01, y=0.05),
                          margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4), width=700, height=450)
        st.plotly_chart(fig)

    ########################
    # Minute Traffic Performance Score
    ########################
    if five_minute_Index:
        st.markdown("## Traffic Performance Score per 5-Minute")
        st.markdown("the 5-Minute dynamic of network-wide traffic changes is interactively demonstrated"
                    "by visualizing the TPS of two types of lanes(Main lane and HOV lane)."
                    "The mouse slides on the curve to flash the 5-Minute TPS data."
                    "Slide the mouse to the upper right corner to display the interactive toolbar")

        sdate_MI = st.date_input('Pick a start date:', value=(datetime.datetime.now() - datetime.timedelta(days=30)))
        edate_MI = st.date_input('Pick an end date:', value=datetime.datetime.now().date())
        st.write('From ', sdate_MI, ' to ', edate_MI, ':')

        df_TI_range = getTrafficIndexMultiDays(sdate_MI, edate_MI)

        # remove outliers from HOV traffic index
        df_TI_range.loc[df_TI_range['avg_vol_hov'] == 0, 'trafficindex_hov'] = 1.0

        df_TI_range['trafficindex_gp'] = df_TI_range['trafficindex_gp'] * 100
        # df_TI_range['trafficindex_gp'] = df_TI_range['trafficindex_gp'].astype('int64')
        df_TI_range['trafficindex_hov'] = df_TI_range['trafficindex_hov'] * 100
        # df_TI_range['trafficindex_hov'] = df_TI_range['trafficindex_hov'].astype('int64')

        sampling_interval = 1
        data = df_TI_range.loc[::sampling_interval, ['time', 'trafficindex_gp', 'trafficindex_hov']]
        lw = 1  # line width
        # Create traces
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data['time'], y=data['trafficindex_gp'],
                                 mode='lines', line=dict(dash='solid', width=lw),
                                 name='Main lane'))
        fig.add_trace(go.Scatter(x=data['time'], y=data['trafficindex_hov'],
                                 mode='lines', line=dict(dash='solid', width=lw),
                                 name='HOV lane'))
        fig.update_layout(xaxis_title='Time', yaxis_title='Traffic Performance Score (%)',
                          legend=dict(x=.01, y=0.05),
                          margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4), width=700, height=450)
        # fig.update_yaxes(range=[0, 1.1])
        st.plotly_chart(fig)

    ########################
    # Minute Traffic Performance Score
    ########################
    if tablular_Data:
        st.markdown("## Network-based Traffic Performance Tablular Data")
        st.markdown("Here, we provide the average volume, average speed, and TPS data of the overall road network every 5 minutes"
                    "for two types of lanes(Main lane and HOV lane)，"
                    "and we also provide data download function in the link of **Download csv file**"
                    "Our verification shows that TPS can more objectively reflect road network traffic performance"
                    "than average traffic and average speed indicators."
                    "We provide 7 data types, including: time,average volume(AVG_Vol_Main),average speed(AVG_Spd_Main),Traffic Performance score(TPS_Main)"
                    "HOV average volume(AVG_Vol_HOV),average speed(AVG_Spd_HOV),Traffic Performance score(TPS_HOV)."
                    "the data type selection is provided through **Show Data Type** drop-down menu."
                    "the data is provided based on selected start and end dates.")
        sdate_TD = st.date_input('Pick a start date', value=(datetime.datetime.now() - datetime.timedelta(days=1)))
        edate_TD = st.date_input('Pick an end date', value=datetime.datetime.now().date())
        st.write('From ', sdate_TD, ' to ', edate_TD, ':')

        df_TI_range = getTrafficIndexMultiDays(sdate_TD, edate_TD)

        # remove outliers from HOV traffic index
        df_TI_range.loc[df_TI_range['avg_vol_hov'] == 0, 'TPS_hov'] = 1.0
        df_TI_range['TPS_Main'] = df_TI_range['TPS_Main'] * 100
        df_TI_range['TPS_hov'] = df_TI_range['TPS_hov'] * 100
        # df_TI_range.columns = ""

        dataFields = st.multiselect('Show Data Type', list(df_TI_range.columns.values),
                                    default=['time','AVG_Spd_Main','AVG_Vol_Main' 'TPS_Main'])
        st.write(df_TI_range[dataFields])

        st.markdown("Download the tabular data as a CSV file:")
        st.markdown(get_table_download_link(df_TI_range[dataFields]), unsafe_allow_html=True)


def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    href = f'<a href="data:file/csv;base64,{b64}" download="data.csv">Download csv file</a>'
    return href


def get_data_from_sel(url, sel):
    session = HTMLSession()
    r = session.get(url)
    mylist = []
    try:
        results = r.html.find(sel)
        for result in results:
            mytext = result.text
            mylist.append(mytext)
        return mylist
    except:
        return None


def update_and_get_covid19_info(url):
    sel_date = '#mw-content-text > div > div.barbox.tright > div > table > tbody > tr > td:nth-child(1)'
    sel_cases = '#mw-content-text > div > div.barbox.tright > div > table > tbody > tr > td:nth-child(3) > span > span:nth-child(1)'
    sel_death = '#mw-content-text > div > div.barbox.tright > div > table > tbody > tr > td:nth-child(4) > span:nth-child(1)'

    try:
        date_list = get_data_from_sel(url, sel_date)
        # the first and last items are not data
        del date_list[len(date_list) - 1]
        del date_list[0]
        cases_list_0 = get_data_from_sel(url, sel_cases)
        death_list_0 = get_data_from_sel(url, sel_death)
        # remove the thousand seprators in cases_list_0 and death_list_0
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        cases_list, death_list = [], [];
        for n in cases_list_0:
            cases_list.append(locale.atoi(n))
        for n in death_list_0:
            death_list.append(locale.atoi(n))

        df_web = pd.DataFrame({'date': date_list, 'confirmed case': cases_list, 'death case': death_list})
        # calculate new case based on confirmed case
        df_web['new case'] = df_web['confirmed case'] - df_web['confirmed case'].shift(1)
        df_web.loc[0, 'new case'] = 0
        df_web['date'] = df_web['date'].astype('datetime64[ns]')

        df_csv = getCOVID19Info()
        df_csv['date'] = df_csv['date'].astype('datetime64[ns]')
        # merge df_web and df_csv
        df_new = df_csv.append(df_web, ignore_index=True)
        df_new = df_new.drop_duplicates(subset=['date'], keep='first')

        if len(df_new) > len(df_csv):
            df_new.to_csv("Washington_COVID_Cases.csv", mode='w', header=True, index=False)

        return getCOVID19Info()

    except:
        return getCOVID19Info()


def showSgementTPS():
    st.markdown("# Segment-based Traffic Preformance Score")

    date = st.date_input('Pick an end date', value=datetime.datetime.now().date())

    datatime1 = datetime.datetime.combine(date, datetime.time(00, 00))
    datatime2 = datetime.datetime.combine(date, datetime.time(23, 59))

    # df_SegTPS_5Min = getSegmentTPS_5Min(datatime1, datatime2)
    # df_SegTPS_5Min.columns = ['time', 'segmentID', 'AVG_Spd_GP', 'AVG_Spd_HOV', 'AVG_Vol_GP', 'AVG_Vol_HOV', 'TrafficIndex_GP', 'TrafficIndex_HOV']

    # time = st.time_input('Pick an end date', value = datetime.datetime.now().time())
    # time = time.replace(second=0, microsecond=0)
    # dt = datetime.datetime.combine(date, time)
    # st.write(dt)
    # st.write(df_SegTPS_5Min)
    # st.write(df_SegTPS_5Min[df_SegTPS_5Min['time'] == dt])

    df_SegTPS = getSegmentTPS_1Hour(datatime1, datatime2)
    df_SegTPS.columns = ['time', 'segmentID', 'AVG_Spd_GP', 'AVG_Spd_HOV', 'AVG_Vol_GP', 'AVG_Vol_HOV',
                         'TrafficIndex_GP', 'TrafficIndex_HOV']

    annimation = True

    # annimation = st.radio( "Display Map", ('Dynamic Map', 'Animated Map')

    # if annimation == 'Dynamic Map':
    # GenerateGeoAnimation(df_SegTPS)
    # else:
    dt = st.selectbox('Select a time', df_SegTPS['time'].astype(str).unique().tolist())
    TPS = df_SegTPS[df_SegTPS['time'] == dt]
    GenerateGeo(TPS)

    # map.save('index.html')
    # # st.write(m._repr_html_(), unsafe_allow_html=True)
    # st.write(map._repr_html_(), unsafe_allow_html=True)

    #####
    st.markdown("# Route-based Traffic Preformance Score")

    sdate = st.date_input('Select a start date', value=(datetime.datetime.now() - datetime.timedelta(days=30)))
    edate = st.date_input('Select an end date', value=datetime.datetime.now().date())

    st.write('From ', sdate, ' to ', edate)

    segments = getSegments()
    segments['label'] = 'Route (' + segments['route'].astype(int).astype(str) + '),\t Direction (' + segments[
        'direction'] + 'B),\t Milepost (' \
                        + segments['milepost_small'].astype(int).astype(str) + ', ' + segments['milepost_large'].astype(
        int).astype(str) + ')'

    segmentLabel = st.selectbox("", segments['label'].iloc[0:10].values.tolist())
    segmentID = segments[segments['label'] == segmentLabel]['segmentid'].values.tolist()[0]
    # st.write(segmentID.values.tolist()[0])
    df_SegTPS_Day = getSegmentTPS_Day(sdate, edate, segmentID)

    # st.write(segments['label'])

    # remove outliers from HOV traffic index
    df_SegTPS_Day.loc[df_SegTPS_Day['avg_vol_hov'] == 0, 'trafficindex_hov'] = 1.0

    df_SegTPS_Day['trafficindex_gp'] = df_SegTPS_Day['trafficindex_gp'] * 100
    # df_TI_range['trafficindex_gp'] = df_TI_range['trafficindex_gp'].astype('int64')
    df_SegTPS_Day['trafficindex_hov'] = df_SegTPS_Day['trafficindex_hov'] * 100
    lw = 1  # line width
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_SegTPS_Day['time'], y=df_SegTPS_Day['trafficindex_gp'],
                             mode='lines', line=dict(dash='solid', width=lw),
                             name='Main lane'))
    fig.add_trace(go.Scatter(x=df_SegTPS_Day['time'], y=df_SegTPS_Day['trafficindex_hov'],
                             mode='lines', line=dict(dash='solid', width=lw),
                             name='HOV lane'))
    fig.update_layout(xaxis_title='Time', yaxis_title='Traffic Performance Score (%)',
                      legend=dict(x=.01, y=0.05),
                      margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4), width=700, height=450)
    # fig.update_yaxes(range=[0, 1.1])
    st.plotly_chart(fig)


def showCOVID19():
    st.markdown("# Impact of COVID-19 on Urban Traffic")
    st.markdown("## COVID-19 in Washington State")
    st.markdown("Since the early March 2020, the coronavirus outbreak has taken hold in the United States. "
                "Besides affecting public health, COVID-19 also has greatly impacted the whole transportation network, "
                "especially when businesses and public agencies shut down. The timeline of responses are listed as below: [\[source\]](https://en.wikipedia.org/wiki/2020_coronavirus_pandemic_in_Washington_(state))")
    st.markdown(
        "* **March 6**: Major tech companies ask Seattle employees to work from home. Amazon and Facebook shut down individual offices as well. [\[link\]](https://www.theverge.com/2020/3/5/21166686/coronavirus-amazon-google-facebook-microsoft-twitter-seattle-staff-remote-work)\n"
        "* **March 9**: UW suspends on-site classes and finals. [\[link\]](https://www.washington.edu/coronavirus/2020/03/06/beginning-march-9-classes-and-finals-will-not-be-held-in-person-message-to-students/) \n"
        "* **March 13**: Gov. Inslee announces statewide school closures, expansion of limits on large gatherings. [\[link\]](https://medium.com/wagovernor/inslee-announces-statewide-school-closures-expansion-of-limits-on-large-gatherings-63d442111438) \n"
        "* **March 16**: Gov. Inslee announces statewide shutdown of restaurants, bars and expanded social gathering limits. [\[link\]](https://www.governor.wa.gov/news-media/inslee-statement-statewide-shutdown-restaurants-bars-and-limits-size-gatherings-expanded) \n"
        "* **March 23**: Gov. Inslee announces \"Stay Home, Stay Healthy\" order. [\[link\]](https://www.governor.wa.gov/news-media/inslee-announces-stay-home-stay-healthy%C2%A0order)\n"
        "* **April 2**: Gov. Inslee extends \"Stay Home, Stay Healthy\" through May 4. [\[link\]](https://www.governor.wa.gov/news-media/inslee-extends-stay-home-stay-healthy-through-may-4))")

    #################################################################
    st.markdown("## COVID-19 Cases")
    st.markdown("The following dynamic plot displays the progression of the coronavirus cases in Washington State.")
    st.write(
        "<iframe src='https://public.flourish.studio/visualisation/1696713/embed' frameborder='0' scrolling='no' style='width:100%;height:600px;'></iframe><div style='width:100%!;margin-top:4px!important;text-align:right!important;'><a class='flourish-credit' href='https://public.flourish.studio/visualisation/1696713/?utm_source=embed&utm_campaign=visualisation/1696713' target='_top' style='text-decoration:none!important'><img alt='Made with Flourish' src='https://public.flourish.studio/resources/made_with_flourish.svg' style='width:105px!important;height:16px!important;border:none!important;margin:0!important;'> </a></div>",
        unsafe_allow_html=True)

    #################################################################
    st.markdown("## Impact of COVID-19 on Urban Traffic")
    st.markdown("This section shows the impact of COVID-19 on urban traffic. "
                "In the following chart, the trends of daily traffic performance scores and the coronavirus cases are displayed together.")

    #################################################################
    # get COVID info and update csv
    url = 'https://en.wikipedia.org/wiki/Template:2019%E2%80%9320_coronavirus_pandemic_data/United_States/Washington_State_medical_cases_chart'
    df_COVID19 = update_and_get_covid19_info(url)
    df_COVID19['date'] = df_COVID19['date'].astype('datetime64[ns]')
    # st.write(df_COVID19)
    # sdate = datetime.datetime(2020, 2, 28)
    # edate = df_COVID19.loc[len(df_COVID19)-1, 'date']
    sdate = st.date_input('Select a start date', value=datetime.datetime(2020, 2, 28))
    edate = st.date_input('Select an end date', value=df_COVID19.loc[len(df_COVID19) - 1, 'date'])
    # daily index
    df_DailyIndex = getDailyIndex(sdate, edate)

    # # remove outliers from HOV traffic index
    # df_DailyIndex.loc[df_DailyIndex['avg_vol_hov'] == 0, 'trafficindex_hov'] = 1.0

    df_DailyIndex['date'] = df_DailyIndex['date'].astype('datetime64[ns]')
    df_DailyIndex = df_DailyIndex[['date', 'daily_index_gp', 'daily_index_hov']]

    df_DailyIndex['daily_index_gp'] = df_DailyIndex['daily_index_gp'] * 100
    # df_DailyIndex['daily_index_gp'] = df_DailyIndex['daily_index_gp'].astype('int64')
    df_DailyIndex['daily_index_hov'] = df_DailyIndex['daily_index_hov'] * 100
    # df_DailyIndex['daily_index_hov'] = df_DailyIndex['daily_index_hov'].astype('int64')

    # # peak volume
    # df_mpv = getMorningPeakVolume(sdate, edate)
    # df_mpv['date'] = df_mpv['date'].astype('datetime64[ns]')
    # df_mpv.rename(columns = {'avg_vol_gp':'Morning_GP', 'avg_vol_hov':'Morning_HOV'}, inplace = True)
    # df_epv = getEveningPeakVolume(sdate, edate)
    # df_epv['date'] = df_epv['date'].astype('datetime64[ns]')
    # df_epv.rename(columns = {'avg_vol_gp':'Evening_GP', 'avg_vol_hov':'Evening_HOV'}, inplace = True)
    # df_pv = pd.merge(df_mpv, df_epv, on='date')

    data = pd.merge(df_DailyIndex, df_COVID19, on='date', how='left')

    # st.write(data['confirmed case'].max())
    confirmed_case_axis_max = data['confirmed case'].max() + 500
    lw = 2  # line width

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces for axis-2
    fig.add_trace(go.Scatter(x=data['date'], y=data['daily_index_gp'],
                             mode='lines', line=dict(dash='dot', width=lw, color='#1f77b4'),
                             name='TPS - GP',
                             legendgroup='group2'),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=data['date'], y=data['daily_index_hov'],
                             mode='lines', line=dict(dash='dot', width=lw, color='#2ca02c'),
                             name='TPS - HOV',
                             legendgroup='group2'),
                  secondary_y=False)

    # Add traces for axis-1
    fig.add_trace(go.Scatter(x=data['date'], y=data['confirmed case'],
                             mode='lines+markers', line=dict(dash='solid', width=lw, color='red'),
                             name='Confirmed Cases',
                             legendgroup='group1'),
                  secondary_y=True)
    fig.add_trace(go.Scatter(x=data['date'], y=data['new case'],
                             mode='lines+markers', line=dict(dash='solid', width=lw, color='orange'),
                             name='New Cases',
                             legendgroup='group1'),
                  secondary_y=True)
    fig.add_trace(go.Scatter(x=data['date'], y=data['death case'],
                             mode='lines+markers', line=dict(dash='solid', width=lw, color='black'),
                             name='Total Death',
                             legendgroup='group1'),
                  secondary_y=True)

    fig.update_traces(textposition='top center')
    # Set x-axis title
    fig.update_xaxes(title_text="Date")
    # Set y-axes titles
    fig.update_yaxes(title_text="Daily Traffic Performance Score (%)",
                     range=[70, 100],
                     showline=True,
                     linecolor='rgb(204, 204, 204)',
                     linewidth=2,
                     showticklabels=True,
                     ticks='outside',
                     secondary_y=False)
    fig.update_yaxes(title_text="COVID-19 Case Amount",
                     range=[0, confirmed_case_axis_max],
                     showline=True,
                     linecolor='rgb(204, 204, 204)',
                     linewidth=2,
                     showticklabels=True,
                     ticks='outside',
                     secondary_y=True)
    fig.update_layout(xaxis=dict(
        showline=True,
        showgrid=False,
        showticklabels=True,
        linecolor='rgb(204, 204, 204)',
        linewidth=2,
        ticks='outside',
        tickfont=dict(
            family='Arial',
            size=12,
            color='rgb(82, 82, 82)',
        ),
    ),
        legend=dict(x=0.5, y=1.3, orientation="h"),
        margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4),
        width=700,
        height=450,
        plot_bgcolor='white')
    st.plotly_chart(fig)

    st.markdown("Download COVID-19 related data as a CSV file:")
    st.markdown(get_table_download_link(data), unsafe_allow_html=True)


def showOtherMetrics():
    ###########
    # Sidebar #
    ###########
    # st.sidebar.markdown("## Components")
    # rushHourVolume = st.sidebar.checkbox("Volume at Rush Hours", value = True)
    rushHourVolume = True

    ########################
    # main content
    ########################
    st.markdown("# Other Traffic Performance Metrics")
    sdate = st.date_input('Select a start date', value=(datetime.datetime.now() - datetime.timedelta(days=30)))
    edate = st.date_input('Select an end date', value=datetime.datetime.now().date())
    st.write('From ', sdate, ' to ', edate)
    if rushHourVolume:
        st.markdown("### Volume per Lane at Rush Hour")

        df_mpv = getMorningPeakVolume(sdate, edate)
        df_mpv['date'] = df_mpv['date'].astype('datetime64[ns]')
        df_mpv.rename(columns={'avg_vol_gp': 'Morning_GP', 'avg_vol_hov': 'Morning_HOV'}, inplace=True)

        df_epv = getEveningPeakVolume(sdate, edate)
        df_epv['date'] = df_epv['date'].astype('datetime64[ns]')
        df_epv.rename(columns={'avg_vol_gp': 'Evening_GP', 'avg_vol_hov': 'Evening_HOV'}, inplace=True)

        df_pv = pd.merge(df_mpv, df_epv, on='date')
        df_pv.set_index('date')
        # print(list(df_pv.columns.values))
        dataFields = st.multiselect('Data fields', ['Morning_GP', 'Evening_GP', 'Morning_HOV', 'Evening_HOV'],
                                    default=['Morning_GP', 'Evening_GP'])

        data = df_pv[['date'] + dataFields]
        lw = 1  # line width
        # Create traces
        fig = go.Figure()
        for item in dataFields:
            fig.add_trace(go.Scatter(x=data['date'], y=data[item],
                                     mode='lines', line=dict(dash='solid', width=lw),
                                     name=item))

        fig.update_layout(xaxis_title='Date', yaxis_title='Traffic Volume per Lane',
                          legend=dict(x=.01, y=0.05),
                          margin=go.layout.Margin(l=50, r=0, b=50, t=10, pad=4), width=700, height=450)

        st.plotly_chart(fig)
        st.markdown("Morning rush hours: 6:00AM-9:00AM; Evening rush hours: 3:00PM-6:00PM")


# st.line_chart(df_pv[dataFields], use_container_width=True)

def showLoopDetectorMap():
    df_loop_location = getLoopDetectorLocation()

    st.pydeck_chart(pdk.Deck(
        # map_style='mapbox://styles/mapbox/dark-v9',
        map_style='mapbox://styles/mapbox/light-v9',
        initial_view_state=pdk.ViewState(
            latitude=47.59,
            longitude=-122.24,
            zoom=9,
            pitch=50,
        ),
        layers=[
            # pdk.Layer(
            #    'HexagonLayer',
            #    data=df_loop_location,
            #    get_position='[lon, lat]',
            #    radius=200,
            #    elevation_scale=4,
            #    elevation_range=[0, 1000],
            #    pickable=True,
            #    extruded=True,
            # ),
            pdk.Layer(
                'ScatterplotLayer',
                data=df_loop_location,
                get_position='[lon, lat]',
                get_color='[0, 160, 187, 160]',
                get_radius=300,
            ),
        ],
    ))


#####################################################
# Main
#####################################################
def main():
    # hide upper-right menu
    hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        </style>
        """
    st.markdown(hide_menu_style, unsafe_allow_html=True)

    # st.title("Traffic Performance Score in Seattle Area")

    st.sidebar.title("Traffic Performance Score")
    app_mode = st.sidebar.radio("Navitation",
                                ["Home", "Network-based TPS", "Segment-based TPS", "Impact of COVID-19",
                                 "Other Traffic Metrics"])
    # st.sidebar.markdown("[![this is an image link](./images/STARLab.png)](https://streamlit.io)")
    if app_mode == "Home":
        IntroduceTrafficIndex()
    elif app_mode == "Network-based TPS":
        showTrafficIndex()
    elif app_mode == "Segment-based TPS":
        showSgementTPS()
    elif app_mode == "Impact of COVID-19":
        showCOVID19()
    elif app_mode == "Other Traffic Metrics":
        showOtherMetrics()

    st.sidebar.title("About")
    st.sidebar.info(
        "This an open source project developed and maintained by the "
        "*Artificial Intelligence GROUP* in the [Smart Transportation Application and Research Lab (**STAR Lab**)](http://www.uwstarlab.org/) "
        "at the [University of Washington](https://www.washington.edu/). "

    )

    st.sidebar.title("Contribute")
    st.sidebar.info(
        "To inquire about potential collaboration, "
        "please contact the **Principal Investigator**: "
        ""
        "[Prof. Yinhai Wang](https://www.ce.washington.edu/facultyfinder/yinhai-wang) ([yinhai@uw.edu](mailto:yinhai@uw.edu))."
    )

    image_starlab = Image.open('images/STARLab.png')
    st.sidebar.image(image_starlab, width=240, use_column_width=False)

    image_pactrans = Image.open('images/PacTrans.png')
    st.sidebar.image(image_pactrans, width=80, use_column_width=False)


# image_uw = Image.open('images/UW2.png')
# st.sidebar.image(image_uw, width = 300, use_column_width=False)

if __name__ == '__main__':
    main()
