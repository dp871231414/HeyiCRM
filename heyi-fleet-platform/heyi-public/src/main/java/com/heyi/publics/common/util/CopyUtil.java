package com.heyi.publics.common.util;

import org.springframework.beans.BeanUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

/**
 * 对象拷贝统一入口（避免各处直接用 BeanUtils 造成行为不一致）。
 */
public final class CopyUtil {

    private CopyUtil() {
    }

    public static <S, T> T copy(S source, Supplier<T> targetSupplier) {
        if (source == null) {
            return null;
        }
        T target = targetSupplier.get();
        BeanUtils.copyProperties(source, target);
        return target;
    }

    public static <S, T> List<T> copyList(List<S> sources, Supplier<T> targetSupplier) {
        List<T> result = new ArrayList<>();
        if (sources == null) {
            return result;
        }
        for (S source : sources) {
            result.add(copy(source, targetSupplier));
        }
        return result;
    }
}
