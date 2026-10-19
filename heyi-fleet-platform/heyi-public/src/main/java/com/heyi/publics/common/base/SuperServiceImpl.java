package com.heyi.publics.common.base;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;

/**
 * Service 默认实现。
 */
public class SuperServiceImpl<M extends BaseMapper<P>, P> extends ServiceImpl<M, P> implements SuperService<P> {
}
