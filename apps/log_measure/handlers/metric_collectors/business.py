# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import datetime

import arrow
from django.db.models import Count

from django.utils.translation import ugettext as _
from django.conf import settings

from apps.log_databus.models import CollectorConfig
from apps.log_search.models import UserIndexSetSearchHistory, LogIndexSet
from apps.log_measure.constants import TIME_RANGE
from apps.log_measure.utils.metric import MetricUtils
from bk_monitor.constants import TimeFilterEnum
from bk_monitor.utils.metric import register_metric, Metric


class BusinessMetricCollector(object):
    @staticmethod
    @register_metric("business_active", description=_("活跃业务"), data_name="metric", time_filter=TimeFilterEnum.MINUTE5)
    def business_active():
        metrics = []
        for timedelta in TIME_RANGE:
            metrics.extend(BusinessMetricCollector().business_active_by_time_range(timedelta))

        return metrics

    @staticmethod
    def business_active_by_time_range(timedelta: str):
        # 一个星期内检索过日志的，才被认为是活跃业务
        end_time = (
            arrow.get(MetricUtils.get_instance().report_ts).to(settings.TIME_ZONE).strftime("%Y-%m-%d %H:%M:%S%z")
        )
        timedelta_v = TIME_RANGE[timedelta]
        start_time = (
            datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S%z") - datetime.timedelta(minutes=timedelta_v)
        ).strftime("%Y-%m-%d %H:%M:%S%z")

        history_ids = UserIndexSetSearchHistory.objects.filter(
            created_at__range=[start_time, end_time],
        ).values_list("index_set_id", flat=True)

        space_uid_list = set(
            LogIndexSet.objects.filter(index_set_id__in=set(history_ids)).values_list("space_uid", flat=True)
        )

        metrics = [
            Metric(
                metric_name="count",
                metric_value=1,
                dimensions={
                    "target_bk_biz_id": MetricUtils.get_instance().project_biz_info[space_uid]["bk_biz_id"],
                    "target_bk_biz_name": MetricUtils.get_instance().project_biz_info[space_uid]["bk_biz_name"],
                    "time_range": timedelta,
                },
                timestamp=MetricUtils.get_instance().report_ts,
            )
            for space_uid in space_uid_list
            if MetricUtils.get_instance().project_biz_info.get(space_uid)
        ]
        metrics.append(
            Metric(
                metric_name="total",
                metric_value=len(space_uid_list),
                dimensions={"time_range": timedelta},
                timestamp=MetricUtils.get_instance().report_ts,
            )
        )

        return metrics

    @staticmethod
    @register_metric("business", description=_("业务"), data_name="metric", time_filter=TimeFilterEnum.MINUTE5)
    def business():
        project_biz_info = MetricUtils.get_instance().project_biz_info
        metrics = [
            Metric(
                metric_name="total",
                metric_value=len(project_biz_info),
                dimensions=None,
                timestamp=MetricUtils.get_instance().report_ts,
            )
        ]
        for bk_biz_id in MetricUtils.get_instance().biz_info:
            metrics.append(
                Metric(
                    metric_name="bk_biz_info",
                    metric_value=1,
                    dimensions={
                        "target_bk_biz_id": bk_biz_id,
                        "target_bk_biz_name": MetricUtils.get_instance().get_biz_name(bk_biz_id),
                    },
                    timestamp=MetricUtils.get_instance().report_ts,
                )
            )

        return metrics

    @staticmethod
    @register_metric(
        "business_collector", description=_("有配置日志采集业务"), data_name="metric", time_filter=TimeFilterEnum.MINUTE5
    )
    def business_collector():
        collector_config_group = (
            CollectorConfig.objects.all().values("bk_biz_id").annotate(total=Count("bk_biz_id")).order_by()
        )
        metrics = []
        total = 0
        for collector_config in collector_config_group:
            metrics.append(
                Metric(
                    metric_name="count",
                    metric_value=collector_config["total"],
                    dimensions={
                        "target_bk_biz_id": collector_config["bk_biz_id"],
                        "target_bk_biz_name": MetricUtils.get_instance().get_biz_name(collector_config["bk_biz_id"]),
                    },
                    timestamp=MetricUtils.get_instance().report_ts,
                )
            )
            total += collector_config["total"]

        metrics.append(
            Metric(
                metric_name="total",
                metric_value=total,
                dimensions=None,
                timestamp=MetricUtils.get_instance().report_ts,
            )
        )

        return metrics
